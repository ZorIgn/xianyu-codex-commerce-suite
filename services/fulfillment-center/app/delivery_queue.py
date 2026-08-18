from __future__ import annotations

import asyncio
import os
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .adapters import XianyuAdapter
from .audit import write_audit
from .db import connect
from .settings_store import get_setting


_MANAGER: "DeliveryQueueManager | None" = None
_LEASE_SECONDS = 90
_DEFAULT_POLL_SECONDS = 0.15


def _now_plus(seconds: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _int_setting(key: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(float(get_setting(key, str(default)))))
    except (TypeError, ValueError):
        return max(minimum, default)


def _float_setting(key: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(get_setting(key, str(default))))
    except (TypeError, ValueError):
        return max(minimum, default)


def _retry_delay(attempt: int) -> float:
    base = _float_setting("delivery_retry_base_seconds", 1.0)
    return min(300.0, base * (2 ** max(0, attempt - 1)))


def _job_dict(job_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM delivery_jobs WHERE id = ?", (int(job_id),)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        outbox = conn.execute(
            """
            SELECT id, order_id, status, attempt, last_error, sent_at, created_at,
                   updated_at
            FROM delivery_outbox
            WHERE job_id = ?
            ORDER BY id ASC
            """,
            (int(job_id),),
        ).fetchall()
    data["outbox"] = [dict(item) for item in outbox]
    return data


def get_delivery_job(order_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM delivery_jobs WHERE order_id = ?", (str(order_id),)
        ).fetchone()
    return _job_dict(int(row["id"])) if row else None


def list_delivery_jobs(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id FROM delivery_jobs ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    return [item for row in rows if (item := _job_dict(int(row["id"]))) is not None]


async def enqueue_delivery_job(
    *,
    order_id: str,
    buyer_id: str = "",
    chat_id: str = "",
    account_id: str = "",
    item_id: str = "",
    platform: str = "chatgpt",
    quantity: int = 1,
    send_to_xianyu: bool = True,
    idempotency_key: str = "",
) -> dict[str, Any]:
    order_id = str(order_id or "").strip()
    if not order_id:
        raise ValueError("order_id is required")
    quantity = max(1, int(quantity or 1))
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO delivery_jobs(
                order_id, buyer_id, chat_id, account_id, item_id, platform, requested_quantity,
                status, send_to_xianyu, idempotency_key, next_run_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, datetime('now'))
            ON CONFLICT(order_id) DO UPDATE SET
                buyer_id = CASE WHEN excluded.buyer_id <> '' THEN excluded.buyer_id ELSE delivery_jobs.buyer_id END,
                chat_id = CASE WHEN excluded.chat_id <> '' THEN excluded.chat_id ELSE delivery_jobs.chat_id END,
                account_id = CASE WHEN excluded.account_id <> '' THEN excluded.account_id ELSE delivery_jobs.account_id END,
                item_id = CASE WHEN excluded.item_id <> '' THEN excluded.item_id ELSE delivery_jobs.item_id END,
                platform = CASE WHEN excluded.platform <> '' THEN excluded.platform ELSE delivery_jobs.platform END,
                requested_quantity = MAX(delivery_jobs.requested_quantity, excluded.requested_quantity),
                send_to_xianyu = excluded.send_to_xianyu,
                idempotency_key = CASE WHEN excluded.idempotency_key <> '' THEN excluded.idempotency_key ELSE delivery_jobs.idempotency_key END,
                status = CASE
                    WHEN delivery_jobs.status = 'sent'
                         AND delivery_jobs.allocated_quantity >= MAX(delivery_jobs.requested_quantity, excluded.requested_quantity)
                    THEN delivery_jobs.status
                    ELSE 'queued'
                END,
                next_run_at = datetime('now'),
                lease_owner = '', lease_expires_at = NULL,
                last_error = '', updated_at = datetime('now')
            """,
            (
                order_id,
                buyer_id,
                chat_id,
                account_id,
                item_id,
                platform,
                quantity,
                1 if send_to_xianyu else 0,
                idempotency_key,
            ),
        )
        row = conn.execute(
            "SELECT id FROM delivery_jobs WHERE order_id = ?", (order_id,)
        ).fetchone()
    if not row:
        raise RuntimeError("delivery job could not be created")
    manager = _manager()
    manager.start()
    job = _job_dict(int(row["id"]))
    if not job:
        raise RuntimeError("delivery job disappeared after creation")
    write_audit(
        "delivery.job_queued",
        order_id=order_id,
        payload={
            "job_id": int(job["id"]),
            "quantity": quantity,
            "send_to_xianyu": bool(send_to_xianyu),
        },
    )
    return job


async def reconcile_delivery_quantity(order_id: str, quantity: int) -> dict[str, Any]:
    quantity = max(1, int(quantity or 1))
    with connect() as conn:
        updated = conn.execute(
            """
            UPDATE delivery_jobs
            SET requested_quantity = MAX(requested_quantity, ?),
                status = CASE WHEN allocated_quantity < ? THEN 'queued' ELSE status END,
                next_run_at = datetime('now'), lease_owner = '', lease_expires_at = NULL,
                last_error = '', reconcile_attempt = reconcile_attempt + 1,
                updated_at = datetime('now')
            WHERE order_id = ?
            """,
            (quantity, quantity, str(order_id)),
        )
    if not updated.rowcount:
        raise KeyError(f"delivery job not found: {order_id}")
    _manager().start()
    result = get_delivery_job(order_id)
    if not result:
        raise KeyError(f"delivery job not found: {order_id}")
    return result


class DeliveryQueueManager:
    def __init__(self) -> None:
        self.owner = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        self.stop_event = asyncio.Event()
        self.task: asyncio.Task[None] | None = None
        self.worker_tasks: dict[int, asyncio.Task[None]] = {}
        self.active_job_ids: set[int] = set()

    def start(self) -> None:
        if self.task and not self.task.done():
            return
        self.stop_event = asyncio.Event()
        self.task = asyncio.create_task(self._run(), name="delivery-queue")

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None
        self.worker_tasks = {}
        self.active_job_ids.clear()

    def _recover_expired(self) -> None:
        with connect() as conn:
            conn.execute(
                """
                UPDATE delivery_jobs
                SET status = CASE WHEN status = 'allocating' THEN 'queued' ELSE 'sending' END,
                    lease_owner = '', lease_expires_at = NULL,
                    next_run_at = datetime('now'), updated_at = datetime('now')
                WHERE status IN ('allocating', 'sending')
                  AND lease_expires_at IS NOT NULL
                  AND lease_expires_at < datetime('now')
                """
            )
            conn.execute(
                """
                UPDATE delivery_outbox
                SET status = 'queued', lease_owner = '', lease_expires_at = NULL,
                    next_attempt_at = datetime('now'), updated_at = datetime('now')
                WHERE status = 'sending'
                  AND lease_expires_at IS NOT NULL
                  AND lease_expires_at < datetime('now')
                """
            )

    def _claim_job(self) -> dict[str, Any] | None:
        # Do not open a writer transaction while the queue is empty. This is
        # important because activation and delivery share the same SQLite file.
        with connect() as conn:
            candidate = conn.execute(
                """
                SELECT id FROM delivery_jobs
                WHERE status IN ('queued', 'sending')
                  AND (next_run_at IS NULL OR next_run_at <= datetime('now'))
                  AND (lease_expires_at IS NULL OR lease_expires_at < datetime('now'))
                ORDER BY id ASC LIMIT 1
                """
            ).fetchone()
        if not candidate:
            return None
        with connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT * FROM delivery_jobs
                WHERE status IN ('queued', 'sending')
                  AND (next_run_at IS NULL OR next_run_at <= datetime('now'))
                  AND (lease_expires_at IS NULL OR lease_expires_at < datetime('now'))
                ORDER BY id ASC LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            job_id = int(row["id"])
            status = "allocating" if int(row["allocated_quantity"] or 0) < int(row["requested_quantity"] or 1) else "sending"
            updated = conn.execute(
                """
                UPDATE delivery_jobs
                SET status = ?, lease_owner = ?, lease_expires_at = ?,
                    allocation_attempts = allocation_attempts + CASE WHEN ? = 'allocating' THEN 1 ELSE 0 END,
                    updated_at = datetime('now')
                WHERE id = ? AND status IN ('queued', 'sending')
                """,
                (status, self.owner, _now_plus(_LEASE_SECONDS), status, job_id),
            )
            if not updated.rowcount:
                return None
            claimed = conn.execute(
                "SELECT * FROM delivery_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return dict(claimed) if claimed else None

    async def _allocate(self, job: dict[str, Any]) -> dict[str, Any]:
        # Import lazily to avoid a module cycle: fulfillment imports the queue
        # only for the payment entry point.
        from .fulfillment import ship_order, get_fulfillment

        result = await ship_order(
            order_id=str(job["order_id"]),
            buyer_id=str(job["buyer_id"] or ""),
            item_id=str(job["item_id"] or ""),
            quantity=int(job["requested_quantity"] or 1),
            platform=str(job["platform"] or "chatgpt"),
            send_to_xianyu=False,
            idempotency_key=str(job["idempotency_key"] or f"delivery-job:{job['order_id']}"),
        )
        fulfillment = get_fulfillment(str(job["order_id"])) or {}
        items = fulfillment.get("items") or result.get("items") or []
        delivery_text = str(result.get("delivery_text") or "")
        if not delivery_text:
            delivery_text = str(fulfillment.get("delivery_text") or "")
        allocated = len(items)
        if allocated < int(job["requested_quantity"] or 1):
            raise RuntimeError(str(result.get("last_error") or "库存不足，发货任务等待重试"))
        return {"allocated_quantity": allocated, "delivery_text": delivery_text}

    def _save_allocated(
        self,
        job: dict[str, Any],
        allocated: int,
        delivery_text: str,
        send: bool,
    ) -> None:
        job_id = int(job["id"])
        with connect() as conn:
            if delivery_text and send:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO delivery_outbox(
                        job_id, order_id, buyer_id, message_text, status, next_attempt_at
                    )
                    SELECT id, order_id, buyer_id, ?, 'queued', datetime('now')
                    FROM delivery_jobs WHERE id = ?
                    """,
                    (delivery_text, job_id),
                )
            elif delivery_text and not send:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO delivery_outbox(
                        job_id, order_id, buyer_id, message_text, status, sent_at, next_attempt_at
                    )
                    SELECT id, order_id, buyer_id, ?, 'sent', datetime('now'), NULL
                    FROM delivery_jobs WHERE id = ?
                    """,
                    (delivery_text, job_id),
                )
            conn.execute(
                """
                UPDATE delivery_jobs
                SET allocated_quantity = ?, delivery_text = ?,
                    status = CASE WHEN ? = 1 THEN 'sending' ELSE 'sent' END,
                    next_run_at = CASE WHEN ? = 1 THEN datetime('now') ELSE NULL END,
                    lease_owner = '', lease_expires_at = NULL,
                    last_error = '', updated_at = datetime('now')
                WHERE id = ?
                """,
                (allocated, delivery_text, 1 if send else 0, 1 if send else 0, job_id),
            )
            conn.execute(
                """
                UPDATE fulfillments
                SET status = CASE WHEN ? = 1 THEN 'send_pending' ELSE 'account_sent' END,
                    buyer_id = CASE WHEN ? <> '' THEN ? ELSE buyer_id END,
                    chat_id = CASE WHEN ? <> '' THEN ? ELSE chat_id END,
                    account_id = CASE WHEN ? <> '' THEN ? ELSE account_id END,
                    last_error = '', updated_at = datetime('now')
                WHERE order_id = ?
                """,
                (
                    1 if send else 0,
                    str(job.get("buyer_id") or ""),
                    str(job.get("buyer_id") or ""),
                    str(job.get("chat_id") or ""),
                    str(job.get("chat_id") or ""),
                    str(job.get("account_id") or ""),
                    str(job.get("account_id") or ""),
                    str(job["order_id"]),
                ),
            )

    def _claim_outbox(self, job_id: int) -> dict[str, Any] | None:
        with connect() as conn:
            candidate = conn.execute(
                """
                SELECT id FROM delivery_outbox
                WHERE job_id = ? AND status = 'queued'
                  AND (next_attempt_at IS NULL OR next_attempt_at <= datetime('now'))
                  AND (lease_expires_at IS NULL OR lease_expires_at < datetime('now'))
                ORDER BY id ASC LIMIT 1
                """,
                (job_id,),
            ).fetchone()
        if not candidate:
            return None
        with connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT * FROM delivery_outbox
                WHERE job_id = ? AND status = 'queued'
                  AND (next_attempt_at IS NULL OR next_attempt_at <= datetime('now'))
                  AND (lease_expires_at IS NULL OR lease_expires_at < datetime('now'))
                ORDER BY id ASC LIMIT 1
                """,
                (job_id,),
            ).fetchone()
            if not row:
                return None
            updated = conn.execute(
                """
                UPDATE delivery_outbox
                SET status = 'sending', attempt = attempt + 1,
                    lease_owner = ?, lease_expires_at = ?, updated_at = datetime('now')
                WHERE id = ? AND status = 'queued'
                """,
                (self.owner, _now_plus(_LEASE_SECONDS), int(row["id"])),
            )
            if not updated.rowcount:
                return None
            claimed = conn.execute(
                "SELECT * FROM delivery_outbox WHERE id = ?", (int(row["id"]),)
            ).fetchone()
        return dict(claimed) if claimed else None

    async def _send_outbox(self, job: dict[str, Any], outbox: dict[str, Any]) -> None:
        try:
            await XianyuAdapter().send_message(
                str(outbox["buyer_id"] or job["buyer_id"] or ""),
                str(outbox["order_id"] or job["order_id"]),
                str(outbox["message_text"] or ""),
                chat_id=str(job.get("chat_id") or ""),
                account_id=str(job.get("account_id") or ""),
            )
        except Exception as exc:
            attempt = int(outbox["attempt"] or 1)
            limit = _int_setting("delivery_retry_limit", 5)
            terminal = attempt >= limit
            with connect() as conn:
                conn.execute(
                    """
                    UPDATE delivery_outbox
                    SET status = ?, next_attempt_at = ?, lease_owner = '', lease_expires_at = NULL,
                        last_error = ?, updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (
                        "failed" if terminal else "queued",
                        None if terminal else _now_plus(_retry_delay(attempt)),
                        str(exc)[:2000],
                        int(outbox["id"]),
                    ),
                )
                conn.execute(
                    """
                    UPDATE delivery_jobs
                    SET status = ?, next_run_at = ?, lease_owner = '', lease_expires_at = NULL,
                        send_attempts = ?, last_error = ?, updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (
                        "failed" if terminal else "sending",
                        None if terminal else _now_plus(_retry_delay(attempt)),
                        attempt,
                        str(exc)[:2000],
                        int(job["id"]),
                    ),
                )
            with connect() as conn:
                conn.execute(
                    """
                    UPDATE fulfillments
                    SET status = 'send_pending', last_error = ?, updated_at = datetime('now')
                    WHERE order_id = ?
                    """,
                    (str(exc)[:2000], str(job["order_id"])),
                )
            write_audit(
                "delivery.outbox_failed" if terminal else "delivery.outbox_retry",
                order_id=str(job["order_id"]),
                payload={"attempt": attempt, "terminal": terminal, "error": str(exc)[:1000]},
            )
            return

        with connect() as conn:
            conn.execute(
                """
                UPDATE delivery_outbox
                SET status = 'sent', sent_at = datetime('now'), next_attempt_at = NULL,
                    lease_owner = '', lease_expires_at = NULL, last_error = '', updated_at = datetime('now')
                WHERE id = ?
                """,
                (int(outbox["id"]),),
            )
            pending = conn.execute(
                "SELECT COUNT(*) AS n FROM delivery_outbox WHERE job_id = ? AND status <> 'sent'",
                (int(job["id"]),),
            ).fetchone()["n"]
            conn.execute(
                """
                UPDATE delivery_jobs
                SET status = ?, next_run_at = ?, lease_owner = '', lease_expires_at = NULL,
                    last_error = '', updated_at = datetime('now')
                WHERE id = ?
                """,
                ("sending" if int(pending or 0) else "sent", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if pending else None, int(job["id"])),
            )
        with connect() as conn:
            conn.execute(
                """
                UPDATE fulfillments
                SET status = ?, last_error = '', updated_at = datetime('now')
                WHERE order_id = ?
                """,
                ("send_pending" if int(pending or 0) else "account_sent", str(job["order_id"])),
            )
        write_audit("delivery.outbox_sent", order_id=str(job["order_id"]), payload={"outbox_id": int(outbox["id"]), "pending": int(pending or 0)})

    async def _process_job(self, job: dict[str, Any]) -> None:
        job_id = int(job["id"])
        try:
            if int(job["allocated_quantity"] or 0) < int(job["requested_quantity"] or 1):
                allocation = await self._allocate(job)
                self._save_allocated(
                    job,
                    int(allocation["allocated_quantity"]),
                    str(allocation["delivery_text"] or ""),
                    bool(job["send_to_xianyu"]),
                )
                job = _job_dict(job_id) or job

            if not bool(job["send_to_xianyu"]):
                with connect() as conn:
                    conn.execute(
                        "UPDATE delivery_jobs SET status='sent', lease_owner='', lease_expires_at=NULL, updated_at=datetime('now') WHERE id=?",
                        (job_id,),
                    )
                return

            outbox = self._claim_outbox(job_id)
            if outbox:
                await self._send_outbox(job, outbox)
            else:
                with connect() as conn:
                    pending = conn.execute(
                        "SELECT COUNT(*) AS n FROM delivery_outbox WHERE job_id = ? AND status <> 'sent'",
                        (job_id,),
                    ).fetchone()["n"]
                    conn.execute(
                        "UPDATE delivery_jobs SET status=?, lease_owner='', lease_expires_at=NULL, updated_at=datetime('now') WHERE id=?",
                        ("sending" if int(pending or 0) else "sent", job_id),
                    )
        except Exception as exc:
            with connect() as conn:
                conn.execute(
                    """
                    UPDATE delivery_jobs
                    SET status='queued', next_run_at=?, lease_owner='', lease_expires_at=NULL,
                        last_error=?, updated_at=datetime('now')
                    WHERE id=?
                    """,
                    (_now_plus(_retry_delay(int(job.get("allocation_attempts") or 1))), str(exc)[:2000], job_id),
                )
            write_audit("delivery.job_retry", order_id=str(job["order_id"]), payload={"error": str(exc)[:1000]})

    async def _worker_loop(self, slot: int) -> None:
        while not self.stop_event.is_set():
            job = self._claim_job()
            if not job:
                await asyncio.sleep(_float_setting("delivery_poll_seconds", _DEFAULT_POLL_SECONDS, 0.05))
                continue
            job_id = int(job["id"])
            self.active_job_ids.add(job_id)
            try:
                await self._process_job(job)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                write_audit("delivery.worker_error", order_id=str(job["order_id"]), payload={"slot": slot, "error": str(exc)[:1000]})
            finally:
                self.active_job_ids.discard(job_id)

    async def _run(self) -> None:
        try:
            last_recovery = 0.0
            while not self.stop_event.is_set():
                now = time.monotonic()
                if now - last_recovery >= 1.0:
                    self._recover_expired()
                    last_recovery = now
                desired = _int_setting("delivery_worker_count", 1)
                for slot in range(desired):
                    task = self.worker_tasks.get(slot)
                    if task is None or task.done():
                        self.worker_tasks[slot] = asyncio.create_task(
                            self._worker_loop(slot), name=f"delivery-worker-{slot}"
                        )
                for slot in list(self.worker_tasks):
                    if slot >= desired:
                        task = self.worker_tasks.pop(slot)
                        task.cancel()
                await asyncio.sleep(0.2)
        finally:
            tasks = list(self.worker_tasks.values())
            self.worker_tasks = {}
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self.active_job_ids.clear()


def _manager() -> DeliveryQueueManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = DeliveryQueueManager()
    return _MANAGER


def start_delivery_worker() -> None:
    _manager().start()


async def stop_delivery_worker() -> None:
    if _MANAGER is not None:
        await _MANAGER.stop()


def delivery_worker_status() -> dict[str, Any]:
    manager = _manager()
    with connect() as conn:
        pending = conn.execute(
            "SELECT COUNT(*) AS n FROM delivery_jobs WHERE status IN ('queued','allocating','sending')"
        ).fetchone()["n"]
    return {
        "running": bool(manager.task and not manager.task.done()),
        "worker_count": len(manager.worker_tasks),
        "worker_capacity": _int_setting("delivery_worker_count", 1),
        "pending_jobs": int(pending or 0),
        "active_job_ids": sorted(manager.active_job_ids),
    }
