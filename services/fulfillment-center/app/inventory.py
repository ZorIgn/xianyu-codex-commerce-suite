from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from .audit import write_audit
from .config import get_settings
from .db import connect
from .settings_store import get_setting


BAD_LIFECYCLE = {"invalid", "expired", "revoked", "disabled", "used", "consumed"}
BAD_DISPLAY = {"invalid", "expired", "revoked", "disabled"}


class InventoryDeleteBlocked(RuntimeError):
    pass


def _pick(data: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return default


def _json_values_from_text(text: str) -> list[Any]:
    """Extract one or more JSON values from pasted text or fenced markdown."""
    value = str(text or "").strip()
    if not value:
        return []
    value = value.replace("```json", "").replace("```JSON", "").replace("```", "").strip()
    try:
        return [json.loads(value)]
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    values: list[Any] = []
    index = 0
    while index < len(value):
        starts = [value.find(marker, index) for marker in ("{", "[")]
        starts = [position for position in starts if position >= 0]
        if not starts:
            break
        start = min(starts)
        try:
            parsed, end = decoder.raw_decode(value[start:])
        except json.JSONDecodeError:
            index = start + 1
            continue
        values.append(parsed)
        index = start + max(1, end)
    return values


def _items_from_cpa(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, str):
        result: list[dict[str, Any]] = []
        for value in _json_values_from_text(payload):
            result.extend(_items_from_cpa(value))
        if result:
            return result
        raise ValueError("没有识别到有效 CPA JSON 对象")
    if isinstance(payload, list):
        result: list[dict[str, Any]] = []
        for value in payload:
            if isinstance(value, dict):
                result.extend(_items_from_cpa(value))
            elif isinstance(value, (list, str)):
                result.extend(_items_from_cpa(value))
        return result
    if isinstance(payload, dict):
        for key in ("items", "accounts", "data", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                return _items_from_cpa(value)
        return [payload]
    raise ValueError("CPA JSON 必须是对象、数组或包含多个对象的文本")


def _credentials_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        result: dict[str, Any] = {}
        direct_keys = (
            "access_token", "accessToken", "refresh_token", "refreshToken",
            "id_token", "idToken", "session_token", "sessionToken",
            "account_id", "accountId", "chatgpt_account_id", "cookies", "cookie",
        )
        for entry in value:
            if not isinstance(entry, dict):
                continue
            key = entry.get("key") or entry.get("name")
            if key and entry.get("value") not in (None, ""):
                result[str(key)] = entry.get("value")
            for direct in direct_keys:
                if entry.get(direct) not in (None, ""):
                    result[direct] = entry.get(direct)
        return result
    return {}


def normalize_account(raw: dict[str, Any]) -> dict[str, Any]:
    credentials = _credentials_dict(raw.get("credentials"))
    overview = raw.get("overview") if isinstance(raw.get("overview"), dict) else {}
    auth = raw.get("https://api.openai.com/auth") if isinstance(raw.get("https://api.openai.com/auth"), dict) else {}
    merged = {**raw, **credentials, **overview, **auth}
    external_seed = _pick(
        merged, "id", "account_id", "accountId", "chatgpt_account_id",
        "user_id", "email", default=json.dumps(raw, sort_keys=True),
    )
    external_id = hashlib.sha256(str(external_seed).encode("utf-8")).hexdigest()
    token_revoked = bool(_pick(merged, "token_revoked", "revoked", "is_revoked", default=False))
    expired = str(_pick(merged, "expired", "expires_at", "expiresAt", default=""))
    platform = str(_pick(merged, "platform", default=get_settings().cpa_platform) or "chatgpt").strip()
    if not platform or platform.lower() == "codex":
        platform = "chatgpt"
    return {
        "external_id": external_id,
        "platform": platform,
        "email": str(_pick(merged, "email", "account", "username", "name", default="")),
        "password": str(_pick(merged, "password", "pwd", default="")),
        "primary_token": str(_pick(merged, "primary_token", "token", "access_token", "accessToken", default="")),
        "session_token": str(_pick(merged, "session_token", "sessionToken", default="")),
        "refresh_token": str(_pick(merged, "refresh_token", "refreshToken", default="")),
        "cookies": str(_pick(merged, "cookies", "cookie", default="")),
        "lifecycle_status": str(_pick(merged, "lifecycle_status", "status", default="registered")),
        "validity_status": str(_pick(merged, "validity_status", default="unknown")),
        "display_status": str(_pick(merged, "display_status", default="registered")),
        "token_revoked": 1 if token_revoked else 0,
        "reset_count": int(_pick(merged, "reset_count", "resetCount", "resets", default=0) or 0),
        "source_payload": json.dumps(raw, ensure_ascii=False),
    }


def import_cpa(payload: Any) -> dict[str, Any]:
    items = [normalize_account(item) for item in _items_from_cpa(payload)]
    created = 0
    updated = 0
    skipped = 0
    details: list[dict[str, Any]] = []

    def add_detail(action: str, inventory_id: int, email: str) -> None:
        if len(details) < 200:
            details.append({"action": action, "inventory_id": inventory_id, "email": email})

    fields = (
        "external_id", "platform", "email", "password", "primary_token",
        "session_token", "refresh_token", "cookies", "lifecycle_status",
        "validity_status", "display_status", "token_revoked", "reset_count",
        "source_payload",
    )
    with connect() as conn:
        for item in items:
            row = conn.execute(
                """
                SELECT * FROM inventory_items
                WHERE external_id = ? OR lower(email) = lower(?)
                ORDER BY id ASC LIMIT 1
                """,
                (item["external_id"], item["email"]),
            ).fetchone()
            if row is None:
                cursor = conn.execute(
                    """
                    INSERT INTO inventory_items(
                        external_id, platform, email, password, primary_token,
                        session_token, refresh_token, cookies, lifecycle_status,
                        validity_status, display_status, token_revoked, reset_count,
                        source_payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    tuple(item[field] for field in fields),
                )
                created += 1
                add_detail("created", int(cursor.lastrowid), str(item["email"]))
                continue

            current = dict(row)
            changed = any(current.get(field) != item[field] for field in fields)
            if not changed:
                skipped += 1
                add_detail("skipped", int(current["id"]), str(current.get("email") or item["email"]))
                continue
            conn.execute(
                """
                UPDATE inventory_items
                SET external_id = ?, platform = ?, email = ?, password = ?,
                    primary_token = ?, session_token = ?, refresh_token = ?,
                    cookies = ?, lifecycle_status = ?, validity_status = ?,
                    display_status = ?, token_revoked = ?, reset_count = ?,
                    source_payload = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (*[item[field] for field in fields], int(current["id"])),
            )
            updated += 1
            add_detail("updated", int(current["id"]), str(item["email"]))

    result = {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total": len(items),
        "details": details,
        "details_truncated": len(items) > len(details),
    }
    write_audit("inventory.import_cpa", payload=result)
    check_low_stock()
    return result


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    try:
        parts = str(token or "").split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def desktop_oauth_status(row: dict[str, Any]) -> dict[str, Any]:
    try:
        raw = json.loads(str(row.get("source_payload") or "{}"))
        raw = raw if isinstance(raw, dict) else {}
    except Exception:
        raw = {}
    credentials = _credentials_dict(raw.get("credentials"))
    merged = {**raw, **credentials}
    access_token = str(row.get("primary_token") or merged.get("access_token") or merged.get("accessToken") or "").strip()
    refresh_token = str(row.get("refresh_token") or merged.get("refresh_token") or merged.get("refreshToken") or "").strip()
    id_token = str(merged.get("id_token") or merged.get("idToken") or "").strip()
    account_id = str(
        merged.get("chatgpt_account_id") or merged.get("account_id") or merged.get("accountId") or ""
    ).strip()
    if not account_id:
        for token in (access_token, id_token):
            claims = _decode_jwt_payload(token)
            auth = claims.get("https://api.openai.com/auth", {})
            if isinstance(auth, dict):
                account_id = str(auth.get("chatgpt_account_id") or auth.get("account_id") or "").strip()
            if account_id:
                break
    fields = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "id_token": id_token,
        "account_id": account_id,
    }
    missing = [name for name, value in fields.items() if not value]
    return {"ready": not missing, "missing": missing}


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
    if not (row["email"] and row["password"]) and not (
        row["primary_token"] or row["session_token"] or row["cookies"]
    ):
        return False, "missing_credentials"
    if settings.activation_provider == "desktop" and not settings.dry_run:
        oauth = desktop_oauth_status(row)
        if not oauth["ready"]:
            return False, "missing_desktop_oauth:" + ",".join(oauth["missing"])
    return True, "ok"


def reserve_many(order_id: str, quantity: int, platform: str = "chatgpt") -> list[dict[str, Any]]:
    quantity = max(1, int(quantity or 1))
    reserved: list[dict[str, Any]] = []
    with connect() as conn:
        # Serialize stock allocation. A deferred transaction can let two
        # concurrent requests read the same available row before either
        # UPDATE runs; only count rows whose conditional UPDATE succeeded.
        conn.execute("BEGIN IMMEDIATE")
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
            updated = conn.execute(
                """
                UPDATE inventory_items
                SET status = 'shipped', reserved_order_id = ?, shipped_at = datetime('now'), updated_at = datetime('now')
                WHERE id = ? AND status = 'available'
                """,
                (order_id, data["id"]),
            )
            if updated.rowcount:
                reserved.append(data)
            if len(reserved) >= quantity:
                break
        if len(reserved) < quantity:
            raise RuntimeError(f"合格库存不足：需要 {quantity} 个，当前只能出库 {len(reserved)} 个")
    for item in reserved:
        write_audit("inventory.shipped", order_id=order_id, inventory_id=item["id"])
    check_low_stock()
    return reserved



def reserve_missing_for_order(
    order_id: str,
    target_quantity: int,
    platform: str = "chatgpt",
) -> list[dict[str, Any]]:
    """Reserve only the missing portion of an already partially shipped order."""
    target_quantity = max(1, int(target_quantity or 1))
    reserved: list[dict[str, Any]] = []
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = int(conn.execute(
            "SELECT COUNT(*) AS n FROM fulfillment_items WHERE order_id = ?",
            (order_id,),
        ).fetchone()["n"] or 0)
        needed = max(0, target_quantity - current)
        if not needed:
            return []
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
            updated = conn.execute(
                """
                UPDATE inventory_items
                SET status = 'shipped', reserved_order_id = ?, shipped_at = datetime('now'), updated_at = datetime('now')
                WHERE id = ? AND status = 'available'
                """,
                (order_id, data["id"]),
            )
            if updated.rowcount:
                reserved.append(data)
            if len(reserved) >= needed:
                break
        if len(reserved) < needed:
            raise RuntimeError(
                f"合格库存不足：订单需要补发 {needed} 个，当前只能补发 {len(reserved)} 个"
            )
    for item in reserved:
        write_audit("inventory.shipped_top_up", order_id=order_id, inventory_id=item["id"])
    check_low_stock()
    return reserved

def mark_activation_started(inventory_id: int, order_id: str, job_id: str = "") -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE inventory_items
            SET status = 'activating', activation_error = '', updated_at = datetime('now')
            WHERE id = ?
            """,
            (inventory_id,),
        )
        conn.execute(
            """
            UPDATE fulfillment_items
            SET status = 'activating', activation_error = '', updated_at = datetime('now')
            WHERE order_id = ? AND inventory_id = ?
            """,
            (order_id, inventory_id),
        )
    write_audit("inventory.activation_started", order_id=order_id, inventory_id=inventory_id, payload={"job_id": job_id})


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
    return "\n".join(parts)


def render_delivery_text(items: list[dict[str, Any]]) -> str:
    template = get_setting("delivery_template")
    accounts = "\n\n".join(
        account_block(item, i + 1 if len(items) > 1 else None)
        for i, item in enumerate(items)
    )
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
        oauth = desktop_oauth_status(item)
        item["desktop_oauth_ready"] = oauth["ready"]
        item["desktop_oauth_missing"] = oauth["missing"]
        item["credential_fields_present"] = {
            "access_token": bool(item.get("primary_token")),
            "refresh_token": bool(item.get("refresh_token")),
            "id_token": "id_token" not in oauth["missing"],
        }
        for secret_field in (
            "password", "primary_token", "session_token", "refresh_token",
            "cookies", "source_payload",
        ):
            item.pop(secret_field, None)
        result.append(item)
    return result


def get_inventory_item(inventory_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM inventory_items WHERE id = ?", (inventory_id,)).fetchone()
    return dict(row) if row else None


def delete_inventory_item(inventory_id: int) -> dict[str, Any]:
    inventory_id = int(inventory_id)
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM inventory_items WHERE id = ?", (inventory_id,)).fetchone()
        if not row:
            raise KeyError(f"库存不存在: {inventory_id}")
        item = dict(row)
        active_jobs = conn.execute(
            """
            SELECT id, status, stage FROM activation_jobs
            WHERE inventory_id = ? AND status NOT IN ('activated', 'failed', 'cancelled')
            ORDER BY id ASC
            """,
            (inventory_id,),
        ).fetchall()
        if active_jobs or str(item.get("status")) == "activating":
            stages = ", ".join(str(job["stage"] or job["status"]) for job in active_jobs) or "activating"
            raise InventoryDeleteBlocked(f"库存正在激活流程中，不能删除（{stages}）")

        batch_rows = conn.execute(
            "SELECT DISTINCT batch_id FROM activation_jobs WHERE inventory_id = ?",
            (inventory_id,),
        ).fetchall()
        batch_ids = [int(value["batch_id"]) for value in batch_rows]
        fulfillment_items = int(conn.execute(
            "SELECT COUNT(*) AS count FROM fulfillment_items WHERE inventory_id = ?",
            (inventory_id,),
        ).fetchone()["count"])
        activation_jobs = int(conn.execute(
            "SELECT COUNT(*) AS count FROM activation_jobs WHERE inventory_id = ?",
            (inventory_id,),
        ).fetchone()["count"])
        conn.execute("UPDATE fulfillments SET inventory_id = NULL, updated_at = datetime('now') WHERE inventory_id = ?", (inventory_id,))
        conn.execute("DELETE FROM fulfillment_items WHERE inventory_id = ?", (inventory_id,))
        conn.execute("DELETE FROM activation_jobs WHERE inventory_id = ?", (inventory_id,))
        deleted_batches = 0
        for batch_id in batch_ids:
            remaining = conn.execute("SELECT 1 FROM activation_jobs WHERE batch_id = ? LIMIT 1", (batch_id,)).fetchone()
            if remaining is None:
                deleted_batches += conn.execute("DELETE FROM activation_batches WHERE id = ?", (batch_id,)).rowcount
        conn.execute("DELETE FROM inventory_items WHERE id = ?", (inventory_id,))

    result = {
        "deleted": True,
        "inventory_id": inventory_id,
        "email": str(item.get("email") or ""),
        "previous_status": str(item.get("status") or ""),
        "removed_fulfillment_items": fulfillment_items,
        "removed_activation_jobs": activation_jobs,
        "removed_activation_batches": deleted_batches,
    }
    write_audit("inventory.deleted", order_id=str(item.get("reserved_order_id") or ""), inventory_id=inventory_id, payload=result)
    check_low_stock()
    return result


def manual_update_status(inventory_id: int, status: str, order_id: str = "") -> dict[str, Any]:
    allowed = {"available", "shipped", "activating", "activated", "activation_failed", "reserved", "consumed"}
    if status not in allowed:
        raise RuntimeError(f"unsupported inventory status: {status}")
    order_id = (order_id or "").strip()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM inventory_items WHERE id = ?", (inventory_id,)).fetchone()
        if not row:
            raise RuntimeError(f"inventory not found: {inventory_id}")
        current = dict(row)
        if status == "available":
            conn.execute(
                """
                UPDATE inventory_items
                SET status = 'available', reserved_order_id = '', shipped_at = NULL,
                    activation_error = '', updated_at = datetime('now')
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
    check_low_stock()
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