from __future__ import annotations

import asyncio
import os
import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .audit import redact_text, write_audit
from .db import connect
from .oauth_reauth import automatic_reauthorize_inventory_oauth_retry


_MANAGER: "OAuthBatchManager | None" = None
_LEASE_SECONDS = 900


def _now_plus(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _safe_error(value: Any) -> str:
    text = redact_text(value)
    for marker in ("access_token", "refresh_token", "id_token", "password"):
        text = text.replace(marker, "credential")
    return text[:2000]


def _batch_dict(batch_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM oauth_refresh_batches WHERE id = ?", (int(batch_id),)
        ).fetchone()
        if not row:
            return None
        jobs = conn.execute(
            """
            SELECT j.id, j.inventory_id, j.status, j.attempt, j.last_error,
                   j.started_at, j.finished_at, i.email
            FROM oauth_refresh_jobs j
            JOIN inventory_items i ON i.id = j.inventory_id
            WHERE j.batch_id = ?
            ORDER BY j.id ASC
            """,
            (int(batch_id),),
        ).fetchall()
    result = dict(row)
    job_dicts = [dict(job) for job in jobs]
    counts = {
        "queued": sum(1 for job in job_dicts if job["status"] == "queued"),
        "succeeded": sum(1 for job in job_dicts if job["status"] == "succeeded"),
        "failed": sum(1 for job in job_dicts if job["status"] == "failed"),
        "cancelled": sum(1 for job in job_dicts if job["status"] == "cancelled"),
    }
    result.update(counts)
    result["total"] = len(job_dicts)
    result["jobs"] = job_dicts
    return result


def list_refresh_batches(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id FROM oauth_refresh_batches ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit), 200)),),
        ).fetchall()
    return [batch for row in rows if (batch := _batch_dict(int(row["id"]))) is not None]


def get_refresh_batch(batch_id: int) -> dict[str, Any] | None:
    return _batch_dict(int(batch_id))


def create_refresh_batch(
    inventory_ids: list[int] | None = None,
    *,
    status_filter: str = "",
    query: str = "",
) -> dict[str, Any]:
    ids = list(dict.fromkeys(int(value) for value in (inventory_ids or [])))
    with connect() as conn:
        if not ids:
            clauses = ["status <> 'consumed'"]
            params: list[Any] = []
            if status_filter:
                clauses.append("status = ?")
                params.append(status_filter)
            if query:
                clauses.append("email LIKE ?")
                params.append(f"%{query}%")
            rows = conn.execute(
                f"SELECT id FROM inventory_items WHERE {' AND '.join(clauses)} ORDER BY id ASC",
                params,
            ).fetchall()
            ids = [int(row["id"]) for row in rows]
        if not ids:
            raise ValueError("没有符合条件的库存")
        existing = conn.execute(
            f"SELECT id FROM inventory_items WHERE id IN ({','.join('?' for _ in ids)})",
            ids,
        ).fetchall()
        existing_ids = {int(row["id"]) for row in existing}
        missing = [value for value in ids if value not in existing_ids]
        if missing:
            raise ValueError("库存不存在: " + ",".join(str(value) for value in missing))
        cursor = conn.execute(
            """
            INSERT INTO oauth_refresh_batches(status, total, queued, updated_at)
            VALUES ('queued', ?, ?, datetime('now'))
            """,
            (len(ids), len(ids)),
        )
        batch_id = int(cursor.lastrowid)
        for inventory_id in ids:
            conn.execute(
                """
                INSERT INTO oauth_refresh_jobs(batch_id, inventory_id, status)
                VALUES (?, ?, 'queued')
                """,
                (batch_id, inventory_id),
            )
    _manager().start()
    write_audit(
        "inventory.oauth_refresh_batch_queued",
        payload={"batch_id": batch_id, "count": len(ids)},
    )
    result = _batch_dict(batch_id)
    if not result:
        raise RuntimeError("OAuth 批量任务创建失败")
    return result


def cancel_refresh_batch(batch_id: int) -> dict[str, Any]:
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        batch = conn.execute(
            "SELECT status FROM oauth_refresh_batches WHERE id = ?", (int(batch_id),)
        ).fetchone()
        if not batch:
            raise KeyError(f"OAuth 批量任务不存在: {batch_id}")
        if str(batch["status"]) in {"completed", "failed", "cancelled", "partial_failed"}:
            return _batch_dict(int(batch_id)) or {}
        conn.execute(
            """
            UPDATE oauth_refresh_jobs
            SET status = 'cancelled', finished_at = datetime('now'), updated_at = datetime('now')
            WHERE batch_id = ? AND status = 'queued'
            """,
            (int(batch_id),),
        )
        conn.execute(
            """
            UPDATE oauth_refresh_batches
            SET status = 'cancelled', updated_at = datetime('now')
            WHERE id = ?
            """,
            (int(batch_id),),
        )
    return _batch_dict(int(batch_id)) or {}


def retry_failed_refresh_jobs(batch_id: int) -> dict[str, Any]:
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        batch = conn.execute(
            "SELECT id FROM oauth_refresh_batches WHERE id = ?", (int(batch_id),)
        ).fetchone()
        if not batch:
            raise KeyError(f"OAuth 批量任务不存在: {batch_id}")
        conn.execute(
            """
            UPDATE oauth_refresh_jobs
            SET status = 'queued', last_error = '', lease_owner = '', lease_expires_at = NULL,
                finished_at = NULL, updated_at = datetime('now')
            WHERE batch_id = ? AND status = 'failed'
            """,
            (int(batch_id),),
        )
        conn.execute(
            """
            UPDATE oauth_refresh_batches
            SET status = 'queued', last_error = '', updated_at = datetime('now')
            WHERE id = ?
            """,
            (int(batch_id),),
        )
    _manager().start()
    return _batch_dict(int(batch_id)) or {}


class OAuthBatchManager:
    """Durable, deliberately single-concurrency OAuth browser worker."""

    def __init__(self) -> None:
        self.owner = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        self.task: asyncio.Task[None] | None = None
        self.stop_event = asyncio.Event()
        self.active_job_id: int | None = None

    def start(self) -> None:
        if self.task and not self.task.done():
            return
        self.stop_event = asyncio.Event()
        self.task = asyncio.create_task(self._run(), name="oauth-refresh-batch")

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None
        self.active_job_id = None

    def _recover(self) -> None:
        with connect() as conn:
            conn.execute(
                """
                UPDATE oauth_refresh_jobs
                SET status = 'queued', lease_owner = '', lease_expires_at = NULL,
                    updated_at = datetime('now')
                WHERE status = 'running' AND lease_expires_at < datetime('now')
                """
            )
            conn.execute(
                """
                UPDATE oauth_refresh_batches
                SET status = 'queued', updated_at = datetime('now')
                WHERE status = 'running'
                  AND id NOT IN (SELECT DISTINCT batch_id FROM oauth_refresh_jobs WHERE status = 'running')
                """
            )

    def _claim(self) -> dict[str, Any] | None:
        with connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT j.*, b.status AS batch_status
                FROM oauth_refresh_jobs j
                JOIN oauth_refresh_batches b ON b.id = j.batch_id
                WHERE j.status = 'queued' AND b.status IN ('queued', 'running')
                ORDER BY j.id ASC LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            updated = conn.execute(
                """
                UPDATE oauth_refresh_jobs
                SET status = 'running', attempt = attempt + 1, lease_owner = ?,
                    lease_expires_at = ?, started_at = COALESCE(started_at, datetime('now')),
                    updated_at = datetime('now')
                WHERE id = ? AND status = 'queued'
                """,
                (self.owner, _now_plus(_LEASE_SECONDS), int(row["id"])),
            )
            if not updated.rowcount:
                return None
            conn.execute(
                "UPDATE oauth_refresh_batches SET status='running', updated_at=datetime('now') WHERE id=? AND status='queued'",
                (int(row["batch_id"]),),
            )
            claimed = conn.execute(
                "SELECT * FROM oauth_refresh_jobs WHERE id = ?", (int(row["id"]),)
            ).fetchone()
        return dict(claimed) if claimed else None

    def _finish_batch(self, batch_id: int) -> None:
        with connect() as conn:
            rows = conn.execute(
                "SELECT status FROM oauth_refresh_jobs WHERE batch_id = ?", (int(batch_id),)
            ).fetchall()
            statuses = [str(row["status"]) for row in rows]
            if any(value in {"queued", "running"} for value in statuses):
                status = "running"
            elif statuses and all(value == "succeeded" for value in statuses):
                status = "completed"
            elif any(value == "succeeded" for value in statuses):
                status = "partial_failed"
            elif any(value == "cancelled" for value in statuses):
                status = "cancelled"
            else:
                status = "failed"
            error_row = conn.execute(
                "SELECT last_error FROM oauth_refresh_jobs WHERE batch_id = ? AND last_error <> '' ORDER BY id DESC LIMIT 1",
                (int(batch_id),),
            ).fetchone()
            conn.execute(
                "UPDATE oauth_refresh_batches SET status=?, last_error=?, updated_at=datetime('now') WHERE id=?",
                (status, _safe_error(error_row["last_error"] if error_row else ""), int(batch_id)),
            )

    async def _process(self, job: dict[str, Any]) -> None:
        job_id = int(job["id"])
        batch_id = int(job["batch_id"])
        self.active_job_id = job_id
        try:
            await asyncio.to_thread(
                automatic_reauthorize_inventory_oauth_retry,
                int(job["inventory_id"]),
            )
        except Exception as exc:
            error = _safe_error(exc)
            with connect() as conn:
                conn.execute(
                    """
                    UPDATE oauth_refresh_jobs
                    SET status='failed', last_error=?, lease_owner='', lease_expires_at=NULL,
                        finished_at=datetime('now'), updated_at=datetime('now')
                    WHERE id=?
                    """,
                    (error, job_id),
                )
            write_audit(
                "inventory.oauth_refresh_batch_job_failed",
                inventory_id=int(job["inventory_id"]),
                payload={"batch_id": batch_id, "job_id": job_id, "error": error},
            )
        else:
            with connect() as conn:
                conn.execute(
                    """
                    UPDATE oauth_refresh_jobs
                    SET status='succeeded', last_error='', lease_owner='', lease_expires_at=NULL,
                        finished_at=datetime('now'), updated_at=datetime('now')
                    WHERE id=?
                    """,
                    (job_id,),
                )
            write_audit(
                "inventory.oauth_refresh_batch_job_succeeded",
                inventory_id=int(job["inventory_id"]),
                payload={"batch_id": batch_id, "job_id": job_id},
            )
        finally:
            self.active_job_id = None
            self._finish_batch(batch_id)

    async def _run(self) -> None:
        self._recover()
        try:
            while not self.stop_event.is_set():
                job = self._claim()
                if not job:
                    await asyncio.sleep(0.5)
                    continue
                await self._process(job)
        finally:
            self.active_job_id = None


def _manager() -> OAuthBatchManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = OAuthBatchManager()
    return _MANAGER


def start_oauth_batch_worker() -> None:
    _manager().start()


async def stop_oauth_batch_worker() -> None:
    if _MANAGER is not None:
        await _MANAGER.stop()


def oauth_batch_status() -> dict[str, Any]:
    manager = _manager()
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM oauth_refresh_jobs WHERE status IN ('queued','running')"
        ).fetchone()
    return {
        "running": bool(manager.task and not manager.task.done()),
        "active_job_id": manager.active_job_id,
        "pending_jobs": int(row["n"] or 0),
        "browser_concurrency": 1,
    }
