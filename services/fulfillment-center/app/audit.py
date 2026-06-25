from __future__ import annotations

import json
from typing import Any

from .db import connect


def write_audit(
    event_type: str,
    *,
    order_id: str = "",
    inventory_id: int | None = None,
    idempotency_key: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO audit_events(order_id, inventory_id, event_type, idempotency_key, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (order_id, inventory_id, event_type, idempotency_key, json.dumps(payload or {}, ensure_ascii=False)),
        )


def list_audit(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_events ORDER BY id DESC LIMIT ?",
            (max(1, min(limit, 500)),),
        ).fetchall()
    return [dict(row) for row in rows]

