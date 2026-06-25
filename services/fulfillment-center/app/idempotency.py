from __future__ import annotations

import json
from typing import Any

from .db import connect


def seen(key: str) -> dict[str, Any] | None:
    if not key:
        return None
    with connect() as conn:
        row = conn.execute("SELECT result FROM idempotency_keys WHERE key = ?", (key,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["result"])
    except json.JSONDecodeError:
        return {"ok": True}


def remember(key: str, *, scope: str, result: dict[str, Any]) -> None:
    if not key:
        return
    with connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO idempotency_keys(key, scope, result)
            VALUES (?, ?, ?)
            """,
            (key, scope, json.dumps(result, ensure_ascii=False)),
        )

