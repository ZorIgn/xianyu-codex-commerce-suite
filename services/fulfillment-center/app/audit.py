from __future__ import annotations

import json
import re
from typing import Any

from .db import connect


_SECRET_KEYS = {
    "password", "passwd", "pwd",
    "access_token", "accesstoken",
    "refresh_token", "refreshtoken",
    "id_token", "idtoken",
    "primary_token", "primarytoken",
    "session_token", "sessiontoken",
    "client_secret", "clientsecret",
    "cookies", "cookie",
    "source_payload", "sourcepayload",
}
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"primary[_-]?token|session[_-]?token|password|passwd|pwd|"
    r"client[_-]?secret)\b\s*[:=]\s*)([\"']?)([^\s,;\"'}&]+)",
)
_SECRET_QUERY = re.compile(
    r"(?i)([?&](?:access_token|refresh_token|id_token|password|client_secret)=)"
    r"[^&\s]+",
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")


def _redact_text(value: str) -> str:
    value = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", value)
    value = _SECRET_QUERY.sub(r"\1[REDACTED]", value)
    value = _BEARER.sub("Bearer [REDACTED]", value)
    return _JWT.sub("[REDACTED_JWT]", value)


def redact_text(value: Any, limit: int = 2000) -> str:
    return _redact_text(str(value or ""))[:max(1, int(limit))]


def _redact(value: Any, *, key: str = "") -> Any:
    normalized_key = re.sub(r"[^a-z0-9_]", "", str(key).lower())
    if normalized_key in _SECRET_KEYS or (
        normalized_key.endswith("token") and normalized_key not in {"token_preview", "tokenpreview"}
    ):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): _redact(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


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
            (order_id, inventory_id, event_type, idempotency_key, json.dumps(_redact(payload or {}), ensure_ascii=False)),
        )


def list_audit(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_events ORDER BY id DESC LIMIT ?",
            (max(1, min(limit, 500)),),
        ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            decoded = json.loads(str(item.get("payload") or "{}"))
            item["payload"] = json.dumps(_redact(decoded), ensure_ascii=False)
        except (TypeError, ValueError, json.JSONDecodeError):
            item["payload"] = _redact_text(str(item.get("payload") or ""))
        result.append(item)
    return result
