from __future__ import annotations

import asyncio
import os
import socket
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from ..adapters import XianyuAdapter
from ..audit import write_audit
from ..config import get_settings
from ..db import connect
from ..inventory import (
    activation_eligibility,
    get_inventory_item,
    mark_activated,
    mark_activation_failed,
    mark_activation_started,
)
from ..settings_store import get_setting
from ..oauth_reauth import automatic_reauthorize_inventory_oauth_retry
from .codex_ws_provider import CodexWsProvider
from .desktop_provider import DesktopInstance, DesktopProvider


_MANAGER: "ActivationQueueManager | None" = None
_WORKER_LOCK_NAME = "desktop-activation"
_WORKER_LEASE_SECONDS = 120
_HEARTBEAT_SECONDS = 15
_ACTIVATION_PROVIDERS = {"cli", "desktop", "ws"}
# 任务级重试只允许在这些“消息一定还没发出”的阶段发生。
_RETRYABLE_PROVIDER_STAGES = {
    "switching_account",
    "starting_desktop",
    "ws_connect_failed",
    "ws_models_failed",
}


def _reauth_before_activation_enabled() -> bool:
    return get_setting("reauth_before_activation", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _setting_int(key: str, fallback: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(float(get_setting(key, str(fallback)))))
    except (TypeError, ValueError):
        return max(minimum, int(fallback))


def _activation_provider() -> str:
    settings = get_settings()
    provider = (
        get_setting("activation_provider", settings.activation_provider)
        .strip()
        .lower()
        or "desktop"
    )
    if provider not in _ACTIVATION_PROVIDERS:
        raise RuntimeError(f"不支持的激活提供方: {provider}")
    return provider


def automatic_reauthorize_inventory_oauth(inventory_id: int) -> dict[str, Any]:
    """Compatibility name; all queue callers still use the retry wrapper."""
    return automatic_reauthorize_inventory_oauth_retry(inventory_id, priority=True)


class ActivationQueueConflict(RuntimeError):
    pass


def _now_plus(seconds: int) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(seconds=seconds)
    ).strftime("%Y-%m-%d %H:%M:%S")


def _batch_dict(batch_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM activation_batches WHERE id = ?",
            (batch_id,),
        ).fetchone()
        if not row:
            return None
        jobs = conn.execute(
            """
            SELECT aj.*, ii.email
            FROM activation_jobs aj
            JOIN inventory_items ii ON ii.id = aj.inventory_id
            WHERE aj.batch_id = ?
            ORDER BY aj.id ASC
            """,
            (batch_id,),
        ).fetchall()
        ahead = conn.execute(
            """
            SELECT COUNT(DISTINCT order_id) AS n
            FROM activation_batches
            WHERE id < ? AND status IN ('queued', 'activating')
            """,
            (batch_id,),
        ).fetchone()["n"]
    data = dict(row)
    data["ahead_orders"] = int(ahead or 0)
    data["jobs"] = [dict(job) for job in jobs]
    return data


def get_activation_batch(batch_id: int) -> dict[str, Any] | None:
    return _batch_dict(int(batch_id))


def list_activation_queue(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id
            FROM activation_batches
            WHERE status IN ('queued', 'activating', 'partial_failed')
            ORDER BY id ASC
            LIMIT ?
            """,
            (max(1, min(limit, 500)),),
        ).fetchall()
    return [
        item
        for row in rows
        if (item := _batch_dict(int(row["id"])))
    ]


def cancel_activation_batch(batch_id: int) -> dict[str, Any]:
    batch_id = int(batch_id)
    order_id = ""
    inventory_ids: list[int] = []
    already_cancelled = False
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        batch = conn.execute(
            "SELECT * FROM activation_batches WHERE id = ?",
            (batch_id,),
        ).fetchone()
        if not batch:
            raise KeyError(f"激活批次不存在: {batch_id}")
        order_id = str(batch["order_id"] or "")
        status = str(batch["status"] or "")
        if status == "cancelled":
            already_cancelled = True
        elif status != "queued":
            raise ActivationQueueConflict(
                f"批次 #{batch_id} 已进入 {status}，只能取消尚未开始的排队任务"
            )

        jobs = conn.execute(
            "SELECT * FROM activation_jobs WHERE batch_id = ? ORDER BY id ASC",
            (batch_id,),
        ).fetchall()
        inventory_ids = [int(job["inventory_id"]) for job in jobs]
        if not already_cancelled:
            started = [
                job
                for job in jobs
                if str(job["status"] or "") not in {"queued", "retry"}
                or job["started_at"] is not None
            ]
            if started:
                raise ActivationQueueConflict(
                    f"批次 #{batch_id} 中已有任务开始执行，已阻止取消"
                )
            conn.execute(
                """
                UPDATE activation_jobs
                SET status = 'cancelled', stage = 'cancelled',
                    error_message = '', lease_owner = '',
                    lease_expires_at = NULL,
                    finished_at = datetime('now'),
                    updated_at = datetime('now')
                WHERE batch_id = ? AND status IN ('queued', 'retry')
                """,
                (batch_id,),
            )
            conn.execute(
                """
                UPDATE activation_batches
                SET status = 'cancelled', current_stage = 'cancelled',
                    worker_owner = '', lease_owner = '',
                    lease_expires_at = NULL, last_error = '',
                    finished_at = datetime('now'),
                    updated_at = datetime('now')
                WHERE id = ? AND status = 'queued'
                """,
                (batch_id,),
            )

            fulfillment_rows = conn.execute(
                "SELECT status FROM fulfillment_items WHERE order_id = ?",
                (order_id,),
            ).fetchall()
            item_statuses = [str(row["status"] or "") for row in fulfillment_rows]
            if item_statuses and all(value == "activated" for value in item_statuses):
                fulfillment_status = "activated"
            elif any(value == "activated" for value in item_statuses):
                fulfillment_status = "partially_activated"
            else:
                fulfillment_status = "account_sent"
            conn.execute(
                """
                UPDATE fulfillments
                SET status = ?, last_error = '', updated_at = datetime('now')
                WHERE order_id = ?
                """,
                (fulfillment_status, order_id),
            )

    if not already_cancelled:
        write_audit(
            "activation.batch_cancelled",
            order_id=order_id,
            payload={
                "batch_id": batch_id,
                "inventory_ids": inventory_ids,
            },
        )
    result = _batch_dict(batch_id)
    if not result:
        raise KeyError(f"激活批次不存在: {batch_id}")
    result["cancelled"] = True
    result["already_cancelled"] = already_cancelled
    return result


def _set_fulfillment_status(
    order_id: str,
    status: str,
    reply: str = "",
    error: str = "",
) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE fulfillments
            SET status = ?, codex_reply = ?, last_error = ?,
                updated_at = datetime('now')
            WHERE order_id = ?
            """,
            (status, reply[:2000], error[:2000], order_id),
        )


class ActivationQueueManager:
    def __init__(self) -> None:
        self.owner = (
            f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        )
        self.stop_event = asyncio.Event()
        self.task: asyncio.Task[None] | None = None
        self.worker_tasks: dict[int, asyncio.Task[None]] = {}
        self.instance_locks: dict[str, asyncio.Lock] = {}
        self.active_batch_ids: set[int] = set()
        self.lock = asyncio.Lock()
        self.current_batch_id: int | None = None
        self.is_leader = False
        self._last_heartbeat = 0.0
        self._last_recovery = 0.0
    def start(self) -> None:
        if self.task and not self.task.done():
            return
        self.stop_event = asyncio.Event()
        self.task = asyncio.create_task(
            self._run(),
            name="activation-worker",
        )

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None
        self.current_batch_id = None
        self.active_batch_ids.clear()
        self.worker_tasks = {}
        self._release_worker_lock()

    def _acquire_worker_lock(self) -> bool:
        with connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT OR IGNORE INTO activation_worker_locks(
                    name, owner, lease_expires_at, updated_at
                )
                VALUES (?, '', NULL, datetime('now'))
                """,
                (_WORKER_LOCK_NAME,),
            )
            updated = conn.execute(
                """
                UPDATE activation_worker_locks
                SET owner = ?, lease_expires_at = ?,
                    updated_at = datetime('now')
                WHERE name = ?
                  AND (
                    owner = ?
                    OR owner = ''
                    OR lease_expires_at IS NULL
                    OR lease_expires_at < datetime('now')
                  )
                """,
                (
                    self.owner,
                    _now_plus(_WORKER_LEASE_SECONDS),
                    _WORKER_LOCK_NAME,
                    self.owner,
                ),
            )
        self.is_leader = bool(updated.rowcount)
        if self.is_leader:
            self._last_heartbeat = time.monotonic()
        return self.is_leader

    def _renew_worker_lock(self) -> bool:
        with connect() as conn:
            updated = conn.execute(
                """
                UPDATE activation_worker_locks
                SET lease_expires_at = ?, updated_at = datetime('now')
                WHERE name = ? AND owner = ?
                """,
                (
                    _now_plus(_WORKER_LEASE_SECONDS),
                    _WORKER_LOCK_NAME,
                    self.owner,
                ),
            )
        self.is_leader = bool(updated.rowcount)
        if self.is_leader:
            self._last_heartbeat = time.monotonic()
        return self.is_leader

    def _release_worker_lock(self) -> None:
        try:
            with connect() as conn:
                conn.execute(
                    """
                    UPDATE activation_worker_locks
                    SET owner = '', lease_expires_at = NULL,
                        updated_at = datetime('now')
                    WHERE name = ? AND owner = ?
                    """,
                    (_WORKER_LOCK_NAME, self.owner),
                )
        except Exception:
            pass
        self.is_leader = False

    def _recover_expired(self) -> None:
        ambiguous_error = (
            "服务中断时桌面消息可能已发送，系统已停止自动重试；"
            "请人工确认后再决定是否重新激活"
        )
        ambiguous: list[dict[str, Any]] = []
        with connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                """
                SELECT id, inventory_id, order_id
                FROM activation_jobs
                WHERE status IN ('sending', 'waiting_response')
                  AND lease_expires_at IS NOT NULL
                  AND lease_expires_at < datetime('now')
                """
            ).fetchall()
            ambiguous = [dict(row) for row in rows]
            for job in ambiguous:
                conn.execute(
                    """
                    UPDATE activation_jobs
                    SET status = 'failed', stage = 'manual_review',
                        error_message = ?, lease_owner = '',
                        lease_expires_at = NULL,
                        finished_at = datetime('now'),
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (ambiguous_error, int(job["id"])),
                )
                conn.execute(
                    """
                    UPDATE inventory_items
                    SET status = 'activation_failed',
                        activation_error = ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (ambiguous_error, int(job["inventory_id"])),
                )
                conn.execute(
                    """
                    UPDATE fulfillment_items
                    SET status = 'activation_failed',
                        activation_error = ?,
                        updated_at = datetime('now')
                    WHERE order_id = ? AND inventory_id = ?
                    """,
                    (
                        ambiguous_error,
                        str(job["order_id"]),
                        int(job["inventory_id"]),
                    ),
                )

            conn.execute(
                """
                UPDATE activation_jobs
                SET status = 'queued', stage = 'queued',
                    lease_owner = '', lease_expires_at = NULL,
                    updated_at = datetime('now')
                WHERE status IN (
                    'switching_account',
                    'reauthorizing',
                    'verifying_account',
                    'opening_codex'
                )
                  AND lease_expires_at IS NOT NULL
                  AND lease_expires_at < datetime('now')
                """
            )
            conn.execute(
                """
                UPDATE activation_batches
                SET status = 'queued', current_stage = 'queued',
                    worker_owner = '', lease_expires_at = NULL,
                    updated_at = datetime('now')
                WHERE status = 'activating'
                  AND lease_expires_at IS NOT NULL
                  AND lease_expires_at < datetime('now')
                """
            )

        for job in ambiguous:
            write_audit(
                "activation.recovered_as_manual_review",
                order_id=str(job["order_id"]),
                inventory_id=int(job["inventory_id"]),
                payload={
                    "job_id": int(job["id"]),
                    "reason": ambiguous_error,
                },
            )
    def _claim_next(self) -> int | None:
        with connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT id
                FROM activation_batches
                WHERE status = 'queued'
                ORDER BY id ASC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            batch_id = int(row["id"])
            updated = conn.execute(
                """
                UPDATE activation_batches
                SET status = 'activating',
                    current_stage = 'switching_account',
                    worker_owner = ?,
                    lease_expires_at = ?,
                    started_at = COALESCE(started_at, datetime('now')),
                    updated_at = datetime('now')
                WHERE id = ? AND status = 'queued'
                """,
                (
                    self.owner,
                    _now_plus(_WORKER_LEASE_SECONDS),
                    batch_id,
                ),
            )
            return batch_id if updated.rowcount else None

    def _claim_job(self, job_id: int) -> dict[str, Any] | None:
        with connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            updated = conn.execute(
                """
                UPDATE activation_jobs
                SET status = 'switching_account',
                    stage = 'switching_account',
                    attempt = attempt + 1,
                    lease_owner = ?,
                    lease_expires_at = ?,
                    started_at = COALESCE(started_at, datetime('now')),
                    updated_at = datetime('now')
                WHERE id = ? AND status IN ('queued', 'retry')
                """,
                (
                    self.owner,
                    _now_plus(_WORKER_LEASE_SECONDS),
                    job_id,
                ),
            )
            if not updated.rowcount:
                return None
            claimed = conn.execute(
                "SELECT * FROM activation_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        return dict(claimed) if claimed else None

    def _set_job_stage(self, job_id: int, stage: str) -> None:
        allowed = {
            "switching_account",
            "reauthorizing",
            "verifying_account",
            "opening_codex",
            "sending",
            "waiting_response",
        }
        if stage not in allowed:
            raise RuntimeError(f"不支持的激活阶段: {stage}")
        lease = _now_plus(_WORKER_LEASE_SECONDS)
        with connect() as conn:
            updated = conn.execute(
                """
                UPDATE activation_jobs
                SET status = ?, stage = ?,
                    lease_expires_at = ?,
                    updated_at = datetime('now')
                WHERE id = ? AND lease_owner = ?
                  AND status NOT IN ('activated', 'failed')
                """,
                (stage, stage, lease, job_id, self.owner),
            )
            conn.execute(
                """
                UPDATE activation_batches
                SET current_stage = ?, lease_expires_at = ?,
                    updated_at = datetime('now')
                WHERE id = (
                    SELECT batch_id
                    FROM activation_jobs
                    WHERE id = ?
                )
                  AND worker_owner = ?
                  AND status = 'activating'
                """,
                (stage, lease, job_id, self.owner),
            )
        if not updated.rowcount:
            raise RuntimeError("激活任务租约已丢失，已阻止桌面发送")
    async def enqueue(
        self,
        *,
        order_id: str,
        buyer_id: str,
        inventory_ids: list[int],
        idempotency_key: str,
        manual: bool = False,
    ) -> dict[str, Any]:
        ids = list(dict.fromkeys(int(value) for value in inventory_ids))
        if not ids:
            raise RuntimeError("没有可激活的库存")

        with connect() as conn:
            existing = conn.execute(
                """
                SELECT id
                FROM activation_batches
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
            if existing:
                batch_id = int(existing["id"])
            else:
                try:
                    cursor = conn.execute(
                        """
                        INSERT INTO activation_batches(
                            order_id, buyer_id, idempotency_key,
                            status, current_stage, provider,
                            quantity, manual
                        )
                        VALUES (?, ?, ?, 'queued', 'queued', ?, ?, ?)
                        """,
                        (
                            order_id,
                            buyer_id,
                            idempotency_key,
                            _activation_provider(),
                            len(ids),
                            1 if manual else 0,
                        ),
                    )
                    batch_id = int(cursor.lastrowid)
                    for inventory_id in ids:
                        conn.execute(
                            """
                            INSERT INTO activation_jobs(
                                batch_id, order_id, inventory_id,
                                status, stage, provider
                            )
                            VALUES (?, ?, ?, 'queued', 'queued', ?)
                            """,
                            (
                                batch_id,
                                order_id,
                                inventory_id,
                                _activation_provider(),
                            ),
                        )
                except sqlite3.IntegrityError:
                    existing = conn.execute(
                        """
                        SELECT id
                        FROM activation_batches
                        WHERE idempotency_key = ?
                        """,
                        (idempotency_key,),
                    ).fetchone()
                    if not existing:
                        raise
                    batch_id = int(existing["id"])

        self.start()
        batch = _batch_dict(batch_id)
        if not batch:
            raise RuntimeError("激活批次创建失败")
        await self._notify_queued(batch)
        return batch

    async def _notify_queued(self, batch: dict[str, Any]) -> None:
        if not batch.get("buyer_id") or str(batch.get("buyer_id")) == "manual":
            return
        with connect() as conn:
            cursor = conn.execute(
                """
                UPDATE activation_batches
                SET queued_notified_at = datetime('now'),
                    updated_at = datetime('now')
                WHERE id = ? AND queued_notified_at IS NULL
                """,
                (batch["id"],),
            )
        if not cursor.rowcount:
            return
        text = (
            "已收到，您的激活任务已进入队列，"
            f"前面还有 {batch.get('ahead_orders', 0)} 单，请稍候。"
        )
        try:
            await XianyuAdapter().send_message(
                str(batch["buyer_id"]),
                str(batch["order_id"]),
                text,
            )
        except Exception as exc:
            write_audit(
                "activation.notify_queued_failed",
                order_id=batch["order_id"],
                payload={"error": str(exc)},
            )

    async def _notify_started(self, batch: dict[str, Any]) -> None:
        if not batch.get("buyer_id") or str(batch.get("buyer_id")) == "manual":
            return
        with connect() as conn:
            cursor = conn.execute(
                """
                UPDATE activation_batches
                SET activating_notified_at = datetime('now'),
                    updated_at = datetime('now')
                WHERE id = ? AND activating_notified_at IS NULL
                """,
                (batch["id"],),
            )
        if not cursor.rowcount:
            return
        try:
            await XianyuAdapter().send_message(
                str(batch["buyer_id"]),
                str(batch["order_id"]),
                "已轮到您的订单，正在为您激活，请稍候。",
            )
        except Exception as exc:
            write_audit(
                "activation.notify_started_failed",
                order_id=batch["order_id"],
                payload={"error": str(exc)},
            )

    async def _notify_finished(
        self,
        batch: dict[str, Any],
        status: str,
    ) -> None:
        if not batch.get("buyer_id") or str(batch.get("buyer_id")) == "manual":
            return
        with connect() as conn:
            cursor = conn.execute(
                """
                UPDATE activation_batches
                SET completed_notified_at = datetime('now'),
                    updated_at = datetime('now')
                WHERE id = ? AND completed_notified_at IS NULL
                """,
                (batch["id"],),
            )
        if not cursor.rowcount:
            return
        text = (
            "您的订单已经激活完成，请刷新后查看。"
            if status == "completed"
            else "本次自动激活未完成，已转入人工处理，请稍候。"
        )
        try:
            await XianyuAdapter().send_message(
                str(batch["buyer_id"]),
                str(batch["order_id"]),
                text,
            )
        except Exception as exc:
            write_audit(
                "activation.notify_finished_failed",
                order_id=batch["order_id"],
                payload={"error": str(exc)},
            )

    async def _provider_result(
        self,
        item: dict[str, Any],
        stage_callback: Callable[[str], None] | None = None,
        instance: DesktopInstance | None = None,
    ) -> dict[str, Any]:
        provider = _activation_provider()
        if provider == "cli":
            from ..codex_runner import run_codex_activation

            result = await run_codex_activation(item)
            return {
                "ok": result.ok,
                "reply": result.reply,
                "error": result.error,
                "stage": "cli",
            }
        if provider == "ws":
            return await CodexWsProvider().activate(
                item,
                "你好",
                stage_callback=stage_callback,
            )
        if provider == "desktop":
            return await DesktopProvider().activate(
                item,
                "你好",
                stage_callback=stage_callback,
                instance=instance,
            )
        raise RuntimeError(f"不支持的激活提供方: {provider}")

    async def _reauthorize_before_activation(
        self, job: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        inventory_id = int(job["inventory_id"])
        order_id = str(job["order_id"])
        job_id = int(job["id"])
        self._set_job_stage(job_id, "reauthorizing")
        write_audit(
            "activation.reauth_before_activation_started",
            order_id=order_id,
            inventory_id=inventory_id,
            payload={"job_id": job_id},
        )
        try:
            result = await asyncio.to_thread(
                automatic_reauthorize_inventory_oauth,
                inventory_id,
            )
        except Exception as exc:
            error = f"激活前重新授权失败: {exc}"
            write_audit(
                "activation.reauth_before_activation_failed",
                order_id=order_id,
                inventory_id=inventory_id,
                payload={"job_id": job_id, "error": error[:2000]},
            )
            return None, error
        fresh_item = get_inventory_item(inventory_id)
        if not fresh_item:
            return None, "重新授权完成后库存不存在"
        write_audit(
            "activation.reauth_before_activation_completed",
            order_id=order_id,
            inventory_id=inventory_id,
            payload={"job_id": job_id, "method": result.get("method", "")},
        )
        return fresh_item, ""

    async def _heartbeat(self, batch_id: int) -> None:
        while True:
            await asyncio.sleep(_HEARTBEAT_SECONDS)
            if not self._renew_worker_lock():
                raise RuntimeError("桌面激活 Worker 已失去全局锁")
            lease = _now_plus(_WORKER_LEASE_SECONDS)
            with connect() as conn:
                conn.execute(
                    """
                    UPDATE activation_batches
                    SET lease_expires_at = ?, updated_at = datetime('now')
                    WHERE id = ? AND status = 'activating'
                      AND worker_owner = ?
                    """,
                    (lease, batch_id, self.owner),
                )
                conn.execute(
                    """
                    UPDATE activation_jobs
                    SET lease_expires_at = ?, updated_at = datetime('now')
                    WHERE batch_id = ? AND lease_owner = ?
                      AND status IN (
                        'switching_account',
                        'reauthorizing',
                        'verifying_account',
                        'opening_codex',
                        'sending',
                        'waiting_response'
                      )
                    """,
                    (lease, batch_id, self.owner),
                )

    async def process_batch(
        self,
        batch_id: int,
        instance: DesktopInstance | None = None,
        slot: int = 0,
    ) -> None:
        if instance is not None:
            instance_key = str(instance.codex_home)
        else:
            # cli / ws 没有实例级共享状态：按 worker 槽位并发，互不阻塞。
            instance_key = f"{_activation_provider()}:slot-{int(slot)}"
        instance_lock = self.instance_locks.setdefault(instance_key, asyncio.Lock())
        async with instance_lock:
            batch = _batch_dict(batch_id)
            if not batch or batch.get("status") in {"completed", "failed"}:
                return

            await self._notify_started(batch)
            jobs = list(batch.get("jobs") or [])
            for original in jobs:
                job = self._claim_job(int(original["id"]))
                if not job:
                    continue
                item = get_inventory_item(int(job["inventory_id"]))
                if not item:
                    with connect() as conn:
                        conn.execute(
                            """
                            UPDATE activation_jobs
                            SET status = 'failed', stage = 'failed',
                                error_message = '库存不存在',
                                lease_owner = '', lease_expires_at = NULL,
                                finished_at = datetime('now'),
                                updated_at = datetime('now')
                            WHERE id = ?
                            """,
                            (job["id"],),
                        )
                    continue

                if _reauth_before_activation_enabled():
                    refreshed_item, reauth_error = await self._reauthorize_before_activation(job)
                    if reauth_error:
                        mark_activation_failed(
                            int(job["inventory_id"]),
                            str(job["order_id"]),
                            reauth_error,
                        )
                        with connect() as conn:
                            conn.execute(
                                """
                                UPDATE activation_jobs
                                SET status = 'failed', stage = 'reauthorization_failed',
                                    error_message = ?, lease_owner = '', lease_expires_at = NULL,
                                    finished_at = datetime('now'), updated_at = datetime('now')
                                WHERE id = ?
                                """,
                                (reauth_error[:2000], int(job["id"])),
                            )
                        continue
                    item = refreshed_item or item
                eligible, eligibility_reason = activation_eligibility(item)
                if not eligible:
                    error = f"库存不可正式激活: {eligibility_reason}"
                    mark_activation_failed(
                        int(job["inventory_id"]),
                        str(job["order_id"]),
                        error,
                    )
                    with connect() as conn:
                        conn.execute(
                            """
                            UPDATE activation_jobs
                            SET status = 'failed', stage = 'ineligible',
                                error_message = ?, lease_owner = '',
                                lease_expires_at = NULL,
                                finished_at = datetime('now'), updated_at = datetime('now')
                            WHERE id = ?
                            """,
                            (error[:2000], int(job["id"])),
                        )
                    continue
                mark_activation_started(
                    int(job["inventory_id"]),
                    str(job["order_id"]),
                    str(job["id"]),
                )
                result: dict[str, Any] = {}
                attempts = max(
                    1,
                    get_settings().desktop_retry_limit + 1,
                )
                for attempt in range(attempts):
                    try:
                        provider_kwargs: dict[str, Any] = {
                            "stage_callback": lambda value, job_id=int(job["id"]): (
                                self._set_job_stage(job_id, value)
                            ),
                        }
                        if instance is not None:
                            provider_kwargs["instance"] = instance
                        result = await self._provider_result(item, **provider_kwargs)
                    except Exception as exc:
                        result = {
                            "ok": False,
                            "error": str(exc),
                            "stage": "provider_error",
                        }
                    if result.get("ok"):
                        break
                    stage = str(result.get("stage") or "")
                    sent_unknown = bool(result.get("sent_unknown"))
                    if (
                        attempt + 1 >= attempts
                        or sent_unknown
                        or stage not in _RETRYABLE_PROVIDER_STAGES
                    ):
                        break
                    await asyncio.sleep(1)

                if result.get("ok"):
                    reply = str(result.get("reply") or "ok")
                    mark_activated(
                        int(job["inventory_id"]),
                        str(job["order_id"]),
                        reply,
                    )
                    with connect() as conn:
                        conn.execute(
                            """
                            UPDATE activation_jobs
                            SET status = 'activated',
                                stage = 'completed',
                                reply_preview = ?,
                                error_message = '',
                                lease_owner = '',
                                lease_expires_at = NULL,
                                finished_at = datetime('now'),
                                updated_at = datetime('now')
                            WHERE id = ?
                            """,
                            (reply[:2000], job["id"]),
                        )
                else:
                    error = str(
                        result.get("error") or "桌面激活失败"
                    )
                    stage = str(result.get("stage") or "failed")
                    mark_activation_failed(
                        int(job["inventory_id"]),
                        str(job["order_id"]),
                        error,
                    )
                    with connect() as conn:
                        conn.execute(
                            """
                            UPDATE activation_jobs
                            SET status = 'failed',
                                stage = ?,
                                error_message = ?,
                                lease_owner = '',
                                lease_expires_at = NULL,
                                finished_at = datetime('now'),
                                updated_at = datetime('now')
                            WHERE id = ?
                            """,
                            (stage, error[:2000], job["id"]),
                        )

                with connect() as conn:
                    conn.execute(
                        """
                        UPDATE activation_batches
                        SET current_stage = ?,
                            lease_expires_at = ?,
                            updated_at = datetime('now')
                        WHERE id = ?
                        """,
                        (
                            "switching_account",
                            _now_plus(_WORKER_LEASE_SECONDS),
                            batch_id,
                        ),
                    )

            await self._finish_batch(batch_id)

    async def _finish_batch(self, batch_id: int) -> None:
        batch = _batch_dict(batch_id)
        if not batch:
            return
        job_statuses = [
            str(job.get("status"))
            for job in batch.get("jobs", [])
        ]
        batch_completed = bool(job_statuses) and all(
            value == "activated" for value in job_statuses
        )
        with connect() as conn:
            order_rows = conn.execute(
                """
                SELECT status
                FROM fulfillment_items
                WHERE order_id = ?
                ORDER BY id ASC
                """,
                (str(batch["order_id"]),),
            ).fetchall()
        order_statuses = [str(row["status"]) for row in order_rows]
        if order_statuses and all(
            value == "activated" for value in order_statuses
        ):
            fulfillment_status = "activated"
        elif any(value == "activated" for value in order_statuses):
            fulfillment_status = "partially_activated"
        elif any(
            value in {"shipped", "activating"}
            for value in order_statuses
        ):
            fulfillment_status = "account_sent"
        else:
            fulfillment_status = "failed"

        status = "completed" if batch_completed else "failed"
        reply = next(
            (
                str(job.get("reply_preview") or "")
                for job in batch.get("jobs", [])
                if job.get("reply_preview")
            ),
            "",
        )
        error = next(
            (
                str(job.get("error_message") or "")
                for job in batch.get("jobs", [])
                if job.get("error_message")
            ),
            "",
        )
        with connect() as conn:
            conn.execute(
                """
                UPDATE activation_batches
                SET status = ?, current_stage = ?, last_error = ?,
                    finished_at = datetime('now'),
                    worker_owner = '', lease_expires_at = NULL,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    status,
                    "completed" if batch_completed else "failed",
                    error[:2000],
                    batch_id,
                ),
            )
        _set_fulfillment_status(
            str(batch["order_id"]),
            fulfillment_status,
            reply,
            error,
        )
        await self._notify_finished(
            _batch_dict(batch_id) or batch,
            status,
        )
        write_audit(
            "activation.batch_finished",
            order_id=str(batch["order_id"]),
            payload={
                "batch_id": batch_id,
                "status": status,
                "fulfillment_status": fulfillment_status,
            },
        )

    def _worker_slots(self) -> list[DesktopInstance | None]:
        settings = get_settings()
        count = _setting_int("activation_worker_count", settings.activation_worker_count)
        provider = _activation_provider()
        if provider in {"cli", "ws"}:
            # 无界面提供方：并发数 = worker 数量，没有实例池限制。
            return [None] * count
        instances = DesktopProvider().resolve_instances()
        return instances[: min(count, len(instances))]

    async def _worker_loop(
        self,
        slot: int,
        instance: DesktopInstance | None,
    ) -> None:
        while not self.stop_event.is_set():
            if not self.is_leader:
                await asyncio.sleep(max(0.5, get_settings().activation_poll_seconds))
                continue
            batch_id = self._claim_next()
            if not batch_id:
                await asyncio.sleep(get_settings().activation_poll_seconds)
                continue
            self.active_batch_ids.add(batch_id)
            self.current_batch_id = min(self.active_batch_ids)
            heartbeat = asyncio.create_task(
                self._heartbeat(batch_id),
                name=f"activation-heartbeat-{slot}-{batch_id}",
            )
            try:
                await self.process_batch(batch_id, instance=instance, slot=slot)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                write_audit(
                    "activation.worker_error",
                    payload={
                        "slot": slot,
                        "batch_id": batch_id,
                        "instance": str(instance.codex_home) if instance else "cli",
                        "error": str(exc),
                    },
                )
                await asyncio.sleep(1)
            finally:
                heartbeat.cancel()
                try:
                    await heartbeat
                except asyncio.CancelledError:
                    pass
                self.active_batch_ids.discard(batch_id)
                self.current_batch_id = min(self.active_batch_ids) if self.active_batch_ids else None

    async def _run(self) -> None:
        try:
            while not self.stop_event.is_set():
                try:
                    if not self.is_leader:
                        if not self._acquire_worker_lock():
                            await asyncio.sleep(
                                max(0.5, get_settings().activation_poll_seconds)
                            )
                            continue
                    elif time.monotonic() - self._last_heartbeat >= _HEARTBEAT_SECONDS:
                        if not self._renew_worker_lock():
                            for task in self.worker_tasks.values():
                                task.cancel()
                            continue

                    now = time.monotonic()
                    if now - self._last_recovery >= 1.0:
                        self._recover_expired()
                        self._last_recovery = now

                    done_slots = [
                        slot for slot, task in self.worker_tasks.items()
                        if task.done()
                    ]
                    for slot in done_slots:
                        task = self.worker_tasks.pop(slot)
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                        except Exception as exc:
                            write_audit(
                                "activation.worker_task_exit",
                                payload={"slot": slot, "error": str(exc)},
                            )

                    try:
                        slots = self._worker_slots()
                    except Exception as exc:
                        write_audit(
                            "activation.instance_pool_error",
                            payload={"error": str(exc)},
                        )
                        await asyncio.sleep(1)
                        continue

                    for slot, instance in enumerate(slots):
                        if slot in self.worker_tasks:
                            continue
                        self.worker_tasks[slot] = asyncio.create_task(
                            self._worker_loop(slot, instance),
                            name=f"activation-worker-{slot}",
                        )
                    await asyncio.sleep(0.2)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    write_audit("activation.worker_error", payload={"error": str(exc)})
                    await asyncio.sleep(1)
        finally:
            tasks = list(self.worker_tasks.values())
            self.worker_tasks = {}
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self.active_batch_ids.clear()
            self.current_batch_id = None
            self._release_worker_lock()

def _manager() -> ActivationQueueManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = ActivationQueueManager()
    return _MANAGER


def start_activation_worker() -> None:
    _manager().start()


async def stop_activation_worker() -> None:
    global _MANAGER
    if _MANAGER is not None:
        await _MANAGER.stop()


async def enqueue_activation_batch(
    *,
    order_id: str,
    buyer_id: str,
    inventory_ids: list[int],
    idempotency_key: str,
    manual: bool = False,
) -> dict[str, Any]:
    return await _manager().enqueue(
        order_id=order_id,
        buyer_id=buyer_id,
        inventory_ids=inventory_ids,
        idempotency_key=idempotency_key,
        manual=manual,
    )


def worker_status() -> dict[str, Any]:
    manager = _manager()
    provider = _activation_provider()
    settings = get_settings()
    pool_error = ""
    instance_count = 0
    if provider == "desktop":
        try:
            instance_count = len(DesktopProvider().resolve_instances())
        except Exception as exc:
            pool_error = str(exc)
    with connect() as conn:
        pending_row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM activation_batches
            WHERE status IN ('queued', 'activating')
            """
        ).fetchone()
        lock_row = conn.execute(
            """
            SELECT owner, lease_expires_at
            FROM activation_worker_locks
            WHERE name = ?
            """,
            (_WORKER_LOCK_NAME,),
        ).fetchone()
    lock_owner = str(lock_row["owner"] or "") if lock_row else ""
    configured_count = _setting_int("activation_worker_count", settings.activation_worker_count)
    if provider == "desktop":
        capacity = min(configured_count, instance_count)
    else:
        capacity = configured_count
    result = {
        "running": bool(manager.task and not manager.task.done()),
        "leader": bool(manager.is_leader and lock_owner == manager.owner),
        "owner": manager.owner,
        "lock_owner": lock_owner,
        "lock_expires_at": str(lock_row["lease_expires_at"] or "") if lock_row else "",
        "current_batch_id": manager.current_batch_id,
        "current_batch_ids": sorted(manager.active_batch_ids),
        "worker_count": len(manager.worker_tasks),
        "worker_capacity": capacity,
        "pending_orders": int(pending_row["n"] or 0),
        "provider": provider,
    }
    if pool_error:
        result["instance_pool_error"] = pool_error
    return result
