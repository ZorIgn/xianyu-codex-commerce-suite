from __future__ import annotations

import hashlib
import json
from typing import Any

from .audit import write_audit
from .config import get_settings
from .db import connect
from .settings_store import get_setting


BAD_LIFECYCLE = {"invalid", "expired", "revoked", "disabled", "used", "consumed"}
BAD_DISPLAY = {"invalid", "expired", "revoked", "disabled"}


def _pick(data: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return default


def _items_from_cpa(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("items", "accounts", "data", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
        return [payload]
    raise ValueError("CPA JSON must be an object or an array")


def _credentials_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        result: dict[str, Any] = {}
        for entry in value:
            if not isinstance(entry, dict):
                continue
            key = entry.get("key") or entry.get("name")
            if key and entry.get("value") not in (None, ""):
                result[str(key)] = entry.get("value")
            for direct in ("access_token", "accessToken", "refresh_token", "refreshToken", "id_token", "idToken", "session_token", "sessionToken", "account_id", "cookies", "cookie"):
                if entry.get(direct) not in (None, ""):
                    result[direct] = entry.get(direct)
        return result
    return {}


def normalize_account(raw: dict[str, Any]) -> dict[str, Any]:
    credentials = _credentials_dict(raw.get("credentials"))
    overview = raw.get("overview") if isinstance(raw.get("overview"), dict) else {}
    auth = raw.get("https://api.openai.com/auth") if isinstance(raw.get("https://api.openai.com/auth"), dict) else {}
    merged = {**raw, **credentials, **overview, **auth}
    external_seed = _pick(merged, "id", "account_id", "chatgpt_account_id", "user_id", "email", default=json.dumps(raw, sort_keys=True))
    external_id = hashlib.sha256(str(external_seed).encode("utf-8")).hexdigest()
    token_revoked = bool(_pick(merged, "token_revoked", "revoked", "is_revoked", default=False))
    expired = str(_pick(merged, "expired", "expires_at", "expiresAt", default=""))
    default_lifecycle = "registered" if not expired else "registered"
    platform = str(_pick(merged, "platform", default=get_settings().cpa_platform) or "chatgpt").strip()
    if not platform or platform.lower() == "codex":
        platform = "chatgpt"
    return {
        "external_id": external_id,
        "platform": platform,
        "email": str(_pick(merged, "email", "account", "username", default="")),
        "password": str(_pick(merged, "password", "pwd", default="")),
        "primary_token": str(_pick(merged, "primary_token", "token", "access_token", "accessToken", default="")),
        "session_token": str(_pick(merged, "session_token", "sessionToken", default="")),
        "refresh_token": str(_pick(merged, "refresh_token", "refreshToken", default="")),
        "cookies": str(_pick(merged, "cookies", "cookie", default="")),
        "lifecycle_status": str(_pick(merged, "lifecycle_status", "status", default=default_lifecycle)),
        "validity_status": str(_pick(merged, "validity_status", default="unknown")),
        "display_status": str(_pick(merged, "display_status", default="registered")),
        "token_revoked": 1 if token_revoked else 0,
        "reset_count": int(_pick(merged, "reset_count", "resetCount", "resets", default=0) or 0),
        "source_payload": json.dumps(raw, ensure_ascii=False),
    }


def import_cpa(payload: Any) -> dict[str, Any]:
    items = [normalize_account(item) for item in _items_from_cpa(payload)]
    created = 0
    skipped = 0
    with connect() as conn:
        for item in items:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO inventory_items(
                    external_id, platform, email, password, primary_token, session_token,
                    refresh_token, cookies, lifecycle_status, validity_status, display_status,
                    token_revoked, reset_count, source_payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["external_id"], item["platform"], item["email"], item["password"],
                    item["primary_token"], item["session_token"], item["refresh_token"], item["cookies"],
                    item["lifecycle_status"], item["validity_status"], item["display_status"],
                    item["token_revoked"], item["reset_count"], item["source_payload"],
                ),
            )
            if cur.rowcount:
                created += 1
            else:
                skipped += 1
    write_audit("inventory.import_cpa", payload={"created": created, "skipped": skipped, "total": len(items)})
    check_low_stock()
    return {"created": created, "skipped": skipped, "total": len(items)}


def is_eligible(row: dict[str, Any]) -> tuple[bool, str]:
    settings = get_settings()
    if row["status"] != "available":
        return False, "not_available"
    if str(row["validity_status"]).lower() == "invalid":
        return False, "invalid_validity"
    if str(row["lifecycle_status"]).lower() in BAD_LIFECYCLE:
        return False, "bad_lifecycle"
    if str(row["display_status"]).lower() in BAD_DISPLAY:
        return False, "bad_display"
    if int(row["token_revoked"] or 0):
        return False, "token_revoked"
    if int(row["reset_count"] or 0) > settings.max_reset_count:
        return False, "reset_count_exceeded"
    if not (row["email"] and row["password"]) and not (row["primary_token"] or row["session_token"] or row["cookies"]):
        return False, "missing_credentials"
    return True, "ok"


def reserve_many(order_id: str, quantity: int, platform: str = "chatgpt") -> list[dict[str, Any]]:
    quantity = max(1, int(quantity or 1))
    reserved: list[dict[str, Any]] = []
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM inventory_items
            WHERE platform = ? AND status = 'available'
            ORDER BY id ASC
            """,
            (platform,),
        ).fetchall()
        for row in rows:
            data = dict(row)
            ok, _ = is_eligible(data)
            if not ok:
                continue
            conn.execute(
                """
                UPDATE inventory_items
                SET status = 'shipped', reserved_order_id = ?, shipped_at = datetime('now'), updated_at = datetime('now')
                WHERE id = ? AND status = 'available'
                """,
                (order_id, data["id"]),
            )
            reserved.append(data)
            if len(reserved) >= quantity:
                break
        if len(reserved) < quantity:
            raise RuntimeError(f"合格库存不足：需要 {quantity} 个，当前只能出库 {len(reserved)} 个")
    for item in reserved:
        write_audit("inventory.shipped", order_id=order_id, inventory_id=item["id"])
    check_low_stock()
    return reserved


def mark_activated(inventory_id: int, order_id: str, reply: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE inventory_items
            SET status = 'activated', activated_at = datetime('now'), codex_reply = ?, activation_error = '', updated_at = datetime('now')
            WHERE id = ?
            """,
            (reply, inventory_id),
        )
        conn.execute(
            """
            UPDATE fulfillment_items
            SET status = 'activated', activation_reply = ?, activation_error = '', updated_at = datetime('now')
            WHERE order_id = ? AND inventory_id = ?
            """,
            (reply, order_id, inventory_id),
        )
    write_audit("inventory.activated", order_id=order_id, inventory_id=inventory_id, payload={"reply": reply[:500]})


def mark_activation_failed(inventory_id: int, order_id: str, error: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE inventory_items
            SET status = 'activation_failed', activation_error = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (error, inventory_id),
        )
        conn.execute(
            """
            UPDATE fulfillment_items
            SET status = 'activation_failed', activation_error = ?, updated_at = datetime('now')
            WHERE order_id = ? AND inventory_id = ?
            """,
            (error, order_id, inventory_id),
        )
    write_audit("inventory.activation_failed", order_id=order_id, inventory_id=inventory_id, payload={"error": error})


def account_block(item: dict[str, Any], index: int | None = None) -> str:
    title = f"账号{index}:" if index else "账号:"
    parts = [title]
    if item.get("email"):
        parts.append(f"邮箱：{item['email']}")
    if item.get("password"):
        parts.append(f"密码：{item['password']}")
    return "\n".join(parts)


def render_delivery_text(items: list[dict[str, Any]]) -> str:
    template = get_setting("delivery_template")
    accounts = "\n\n".join(account_block(item, i + 1 if len(items) > 1 else None) for i, item in enumerate(items))
    return template.replace("{accounts}", accounts).replace("{count}", str(len(items)))


def list_inventory(status: str = "", q: str = "", limit: int = 200) -> list[dict[str, Any]]:
    clauses = []
    params: list[Any] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if q:
        clauses.append("(email LIKE ? OR reserved_order_id LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM inventory_items{where} ORDER BY id DESC LIMIT ?",
            (*params, max(1, min(limit, 1000))),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        ok, reason = is_eligible(item)
        item["eligible"] = ok
        item["eligible_reason"] = reason
        result.append(item)
    return result


def get_inventory_item(inventory_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM inventory_items WHERE id = ?", (inventory_id,)).fetchone()
    return dict(row) if row else None




def manual_update_status(inventory_id: int, status: str, order_id: str = "") -> dict[str, Any]:
    allowed = {"available", "shipped", "activated", "activation_failed", "reserved", "consumed"}
    if status not in allowed:
        raise RuntimeError(f"unsupported inventory status: {status}")
    order_id = (order_id or "").strip()
    with connect() as conn:
        row = conn.execute("SELECT * FROM inventory_items WHERE id = ?", (inventory_id,)).fetchone()
        if not row:
            raise RuntimeError(f"inventory not found: {inventory_id}")
        current = dict(row)
        if status == "available":
            conn.execute(
                """
                UPDATE inventory_items
                SET status = 'available', reserved_order_id = '', shipped_at = NULL, activation_error = '', updated_at = datetime('now')
                WHERE id = ?
                """,
                (inventory_id,),
            )
        else:
            if status in {"shipped", "activated", "activation_failed"} and not order_id:
                order_id = current.get("reserved_order_id") or f"manual-{status}-{inventory_id}"
            conn.execute(
                """
                UPDATE inventory_items
                SET status = ?, reserved_order_id = CASE WHEN ? = '' THEN reserved_order_id ELSE ? END,
                    shipped_at = CASE WHEN ? IN ('shipped', 'activated', 'activation_failed') THEN COALESCE(shipped_at, datetime('now')) ELSE shipped_at END,
                    activated_at = CASE WHEN ? = 'activated' THEN COALESCE(activated_at, datetime('now')) ELSE activated_at END,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (status, order_id, order_id, status, status, inventory_id),
            )
            if order_id and status in {"shipped", "activated", "activation_failed"}:
                conn.execute(
                    """
                    INSERT INTO fulfillments(order_id, buyer_id, item_id, quantity, status, delivery_text, updated_at)
                    VALUES (?, 'manual', 'manual', 1, ?, '', datetime('now'))
                    ON CONFLICT(order_id) DO UPDATE SET status = excluded.status, updated_at = datetime('now')
                    """,
                    (order_id, "activated" if status == "activated" else "account_sent"),
                )
                conn.execute(
                    """
                    INSERT INTO fulfillment_items(order_id, inventory_id, status)
                    VALUES (?, ?, ?)
                    ON CONFLICT(order_id, inventory_id) DO UPDATE SET status = excluded.status, updated_at = datetime('now')
                    """,
                    (order_id, inventory_id, "activated" if status == "activated" else "shipped"),
                )
    write_audit("inventory.manual_status", order_id=order_id, inventory_id=inventory_id, payload={"status": status})
    item = get_inventory_item(inventory_id)
    return item or {}

def summary() -> dict[str, Any]:
    with connect() as conn:
        counts = conn.execute("SELECT status, COUNT(*) AS n FROM inventory_items GROUP BY status ORDER BY status").fetchall()
        rows = conn.execute("SELECT * FROM inventory_items WHERE status = 'available'").fetchall()
        alerts = conn.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT 20").fetchall()
    eligible = sum(1 for row in rows if is_eligible(dict(row))[0])
    return {
        "by_status": {row["status"]: row["n"] for row in counts},
        "eligible": eligible,
        "alerts": [dict(row) for row in alerts],
    }


def check_low_stock() -> None:
    settings = get_settings()
    current = summary().get("eligible", 0)
    if current >= settings.low_stock_threshold:
        return
    with connect() as conn:
        conn.execute(
            "INSERT INTO alerts(kind, message, payload) VALUES ('low_stock', ?, ?)",
            (
                f"合格库存不足 {settings.low_stock_threshold} 个，当前 {current} 个",
                json.dumps({"eligible": current, "threshold": settings.low_stock_threshold}, ensure_ascii=False),
            ),
        )
