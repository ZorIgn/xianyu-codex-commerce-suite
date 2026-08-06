from __future__ import annotations

import re
from typing import Any

from .adapters import XianyuAdapter
from .config import get_settings
from .audit import write_audit
from .db import connect
from .delivery_queue import enqueue_delivery_job
from .idempotency import remember, seen
from .inventory import (
    get_inventory_item,
    render_delivery_text,
    reserve_many,
    reserve_missing_for_order,
)
from .activation.queue import (
    enqueue_activation_batch,
    get_activation_batch,
)


def _compact_message_text(text: str) -> str:
    return "".join(ch for ch in (text or "").lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def is_activation_trigger(text: str) -> bool:
    return "全部邮箱无误已邀请" in _compact_message_text(text)


def is_invite_like_message(text: str) -> bool:
    normalized = _compact_message_text(text)
    if is_activation_trigger(text):
        return True
    return any(
        kw in normalized
        for kw in (
            "已邀请", "邀请了", "邀了", "发邀请", "发送邀请", "发送了",
            "发了", "弄好了", "好了", "ok", "okay", "完成了", "可以了",
        )
    )


def _latest_activation_batch(order_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM activation_batches WHERE order_id = ? ORDER BY id DESC LIMIT 1",
            (order_id,),
        ).fetchone()
    return get_activation_batch(int(row["id"])) if row else None


def get_fulfillment(order_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM fulfillments WHERE order_id = ?", (order_id,)).fetchone()
        if not row:
            return None
        items = conn.execute(
            """
            SELECT fi.*, ii.email, ii.status AS inventory_status, ii.activated_at,
                   ii.activation_error AS inventory_activation_error
            FROM fulfillment_items fi
            JOIN inventory_items ii ON ii.id = fi.inventory_id
            WHERE fi.order_id = ?
            ORDER BY fi.id ASC
            """,
            (order_id,),
        ).fetchall()
    data = dict(row)
    data["items"] = [dict(item) for item in items]
    data["activation_batch"] = _latest_activation_batch(order_id)
    return data


def list_fulfillments(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM fulfillments ORDER BY id DESC LIMIT ?",
            (max(1, min(limit, 500)),),
        ).fetchall()
    return [dict(row) for row in rows]


def _save_fulfillment(
    *,
    order_id: str,
    buyer_id: str,
    chat_id: str = "",
    account_id: str = "",
    item_id: str = "",
    quantity: int = 1,
    status: str,
    delivery_text: str = "",
    error: str = "",
) -> dict[str, Any]:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO fulfillments(order_id, buyer_id, chat_id, account_id, item_id, quantity, status, delivery_text, last_error, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(order_id) DO UPDATE SET
                buyer_id = excluded.buyer_id,
                chat_id = CASE WHEN excluded.chat_id <> '' THEN excluded.chat_id ELSE fulfillments.chat_id END,
                account_id = CASE WHEN excluded.account_id <> '' THEN excluded.account_id ELSE fulfillments.account_id END,
                item_id = excluded.item_id,
                quantity = excluded.quantity,
                status = excluded.status,
                delivery_text = excluded.delivery_text,
                last_error = excluded.last_error,
                updated_at = datetime('now')
            """,
            (order_id, buyer_id, chat_id, account_id, item_id, quantity, status, delivery_text, error),
        )
        row = conn.execute("SELECT * FROM fulfillments WHERE order_id = ?", (order_id,)).fetchone()
    return dict(row)


async def _send_persisted_delivery(order_id: str, buyer_id: str, text: str) -> tuple[bool, str]:
    try:
        await XianyuAdapter().send_message(buyer_id, order_id, text)
    except Exception as exc:
        error = str(exc)
        with connect() as conn:
            conn.execute(
                """
                UPDATE fulfillments
                SET status = 'send_pending', last_error = ?, updated_at = datetime('now')
                WHERE order_id = ?
                """,
                (error[:2000], order_id),
            )
        return False, error
    with connect() as conn:
        conn.execute(
            """
            UPDATE fulfillments
            SET status = 'account_sent', last_error = '', updated_at = datetime('now')
            WHERE order_id = ?
            """,
            (order_id,),
        )
    return True, ""


async def _ship_missing_items(
    *,
    order_id: str,
    buyer_id: str,
    item_id: str,
    target_quantity: int,
    platform: str,
    send_to_xianyu: bool,
) -> dict[str, Any]:
    """Reserve only the missing portion and keep a failed send retryable."""
    items = reserve_missing_for_order(order_id, target_quantity, platform=platform)
    if not items:
        result = get_fulfillment(order_id) or {}
        result["idempotent"] = True
        result["top_up"] = False
        result["delivery_text"] = ""
        return result

    new_delivery_text = render_delivery_text(items)
    with connect() as conn:
        row = conn.execute(
            "SELECT quantity, delivery_text FROM fulfillments WHERE order_id = ?",
            (order_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("top-up fulfillment record does not exist")
        previous_text = str(row["delivery_text"] or "")
        combined_text = f"{previous_text}\n\n{new_delivery_text}".strip() if previous_text else new_delivery_text
        conn.execute(
            """
            UPDATE fulfillments
            SET buyer_id = COALESCE(NULLIF(?, ''), buyer_id),
                item_id = COALESCE(NULLIF(?, ''), item_id),
                quantity = MAX(quantity, ?),
                status = ?, delivery_text = ?, last_error = '', updated_at = datetime('now')
            WHERE order_id = ?
            """,
            (buyer_id, item_id, int(target_quantity), "sending" if send_to_xianyu else "account_sent", combined_text, order_id),
        )
        for item in items:
            conn.execute(
                "INSERT OR IGNORE INTO fulfillment_items(order_id, inventory_id, status) VALUES (?, ?, 'shipped')",
                (order_id, item["id"]),
            )

    send_error = ""
    if send_to_xianyu and new_delivery_text:
        _, send_error = await _send_persisted_delivery(order_id, buyer_id, new_delivery_text)
    result = get_fulfillment(order_id) or {}
    result["delivery_text"] = new_delivery_text
    result["top_up"] = True
    result["quantity_added"] = len(items)
    result["send_pending"] = bool(send_error)
    if send_error:
        result["last_error"] = send_error
    write_audit(
        "fulfillment.ship_order_top_up",
        order_id=order_id,
        payload={"quantity": target_quantity, "quantity_added": len(items), "send_pending": bool(send_error)},
    )
    return result


async def ship_order(
    *,
    order_id: str,
    buyer_id: str = "",
    item_id: str = "",
    quantity: int = 1,
    platform: str = "chatgpt",
    send_to_xianyu: bool = True,
    idempotency_key: str = "",
) -> dict[str, Any]:
    quantity = max(1, int(quantity or 1))
    existing = get_fulfillment(order_id)
    existing_count = len((existing or {}).get("items") or [])
    if existing and existing_count >= quantity:
        retry_send = bool(send_to_xianyu and existing.get("delivery_text") and existing.get("status") in {"send_pending", "sending", "failed"})
        send_error = ""
        if retry_send:
            _, send_error = await _send_persisted_delivery(order_id, buyer_id or str(existing.get("buyer_id") or ""), str(existing.get("delivery_text") or ""))
        result = get_fulfillment(order_id) or existing
        result["idempotent"] = True
        result["top_up"] = False
        result["send_pending"] = bool(send_error)
        result["delivery_text"] = str(existing.get("delivery_text") or "") if retry_send and not send_error else ""
        if send_error:
            result["last_error"] = send_error
        return result

    if existing and existing_count:
        try:
            result = await _ship_missing_items(
                order_id=order_id,
                buyer_id=buyer_id,
                item_id=item_id,
                target_quantity=quantity,
                platform=platform,
                send_to_xianyu=send_to_xianyu,
            )
            remember(idempotency_key, scope="ship_order", result=result)
            return result
        except Exception as exc:
            current = get_fulfillment(order_id) or existing
            current["last_error"] = str(exc)
            write_audit(
                "fulfillment.ship_order_top_up_failed",
                order_id=order_id,
                payload={"error": str(exc), "target_quantity": quantity},
            )
            return current

    cache = seen(idempotency_key)
    if cache:
        return {"idempotent": True, **cache}

    try:
        items = reserve_many(order_id, quantity, platform=platform)
        delivery_text = render_delivery_text(items)
        _save_fulfillment(
            order_id=order_id, buyer_id=buyer_id, item_id=item_id,
            quantity=quantity, status="sending" if send_to_xianyu else "account_sent", delivery_text=delivery_text,
        )
        with connect() as conn:
            for item in items:
                conn.execute(
                    "INSERT OR IGNORE INTO fulfillment_items(order_id, inventory_id, status) VALUES (?, ?, 'shipped')",
                    (order_id, item["id"]),
                )
        send_error = ""
        if send_to_xianyu:
            _, send_error = await _send_persisted_delivery(order_id, buyer_id, delivery_text)
        result = get_fulfillment(order_id) or {}
        result["delivery_text"] = delivery_text
        result["send_pending"] = bool(send_error)
        if send_error:
            result["last_error"] = send_error
        write_audit(
            "fulfillment.ship_order",
            order_id=order_id,
            idempotency_key=idempotency_key,
            payload={"quantity": quantity, "send_to_xianyu": send_to_xianyu, "send_pending": bool(send_error)},
        )
    except Exception as exc:
        result = _save_fulfillment(
            order_id=order_id, buyer_id=buyer_id, item_id=item_id,
            quantity=quantity, status="failed", error=str(exc),
        )
        write_audit("fulfillment.ship_order_failed", order_id=order_id, payload={"error": str(exc)})
    remember(idempotency_key, scope="ship_order", result=result)
    return result


async def handle_order_paid(
    *,
    order_id: str,
    buyer_id: str = "",
    item_id: str = "",
    platform: str = "chatgpt",
    quantity: int = 1,
    chat_id: str = "",
    account_id: str = "",
    idempotency_key: str = "",
) -> dict[str, Any]:
    if not str(chat_id or "").strip():
        raise ValueError("chat_id is required for a paid order")
    if not str(account_id or "").strip():
        raise ValueError("account_id is required for a paid order")
    job = await enqueue_delivery_job(
        order_id=order_id,
        buyer_id=buyer_id,
        chat_id=chat_id,
        account_id=account_id,
        item_id=item_id,
        platform=platform,
        quantity=quantity,
        send_to_xianyu=True,
        idempotency_key=idempotency_key or f"order-paid:{order_id}",
    )
    return {
        "ok": True,
        "queued": True,
        "order_id": order_id,
        "status": job.get("status", "queued"),
        "delivery_job": job,
    }


async def _ensure_activation_item(order_id: str, inventory_id: int) -> dict[str, Any]:
    item = get_inventory_item(inventory_id)
    if not item:
        raise RuntimeError(f"库存不存在: {inventory_id}")
    existing_order = item.get("reserved_order_id") or ""
    order_id = existing_order or order_id
    fulfillment = get_fulfillment(order_id)
    if not fulfillment:
        delivery_text = render_delivery_text([item])
        _save_fulfillment(
            order_id=order_id, buyer_id="manual", item_id="manual",
            quantity=1, status="account_sent", delivery_text=delivery_text,
        )
        with connect() as conn:
            conn.execute(
                """
                UPDATE inventory_items
                SET status = CASE WHEN status = 'available' THEN 'shipped' ELSE status END,
                    reserved_order_id = CASE WHEN reserved_order_id = '' THEN ? ELSE reserved_order_id END,
                    shipped_at = CASE WHEN shipped_at IS NULL THEN datetime('now') ELSE shipped_at END,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (order_id, inventory_id),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO fulfillment_items(order_id, inventory_id, status)
                VALUES (?, ?, 'shipped')
                """,
                (order_id, inventory_id),
            )
    else:
        with connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO fulfillment_items(order_id, inventory_id, status)
                VALUES (?, ?, 'shipped')
                """,
                (order_id, inventory_id),
            )
    return get_inventory_item(inventory_id) or item


async def activate_inventory_item(order_id: str, inventory_id: int) -> dict[str, Any]:
    requested_order_id = (order_id or "").strip() or f"manual-activate-{inventory_id}"
    item = await _ensure_activation_item(requested_order_id, inventory_id)
    actual_order_id = str(item.get("reserved_order_id") or requested_order_id)
    fulfillment = get_fulfillment(actual_order_id) or {}
    write_audit("fulfillment.activate.queued", order_id=actual_order_id, inventory_id=inventory_id)
    batch = await enqueue_activation_batch(
        order_id=actual_order_id,
        buyer_id=str(fulfillment.get("buyer_id") or "manual"),
        inventory_ids=[inventory_id],
        idempotency_key=f"manual-activate:{actual_order_id}:{inventory_id}:{requested_order_id}",
        manual=True,
    )
    with connect() as conn:
        conn.execute(
            "UPDATE fulfillments SET status='activation_queued', updated_at=datetime('now') WHERE order_id=?",
            (actual_order_id,),
        )
    if batch.get("status") == "queued" and get_settings().dry_run:
        from .activation.queue import _manager
        manager = _manager()
        await manager.process_batch(int(batch["id"]))
    result = get_fulfillment(actual_order_id) or {}
    result["activation_batch"] = get_activation_batch(int(batch["id"]))
    return result


async def activate_order(order_id: str) -> dict[str, Any]:
    fulfillment = get_fulfillment(order_id)
    if not fulfillment:
        raise RuntimeError(f"订单不存在: {order_id}")
    targets = [
        item for item in fulfillment.get("items", [])
        if item.get("status") in {"shipped", "activation_failed", "activating"}
    ]
    if not targets:
        return fulfillment
    batch = await enqueue_activation_batch(
        order_id=order_id,
        buyer_id=str(fulfillment.get("buyer_id") or ""),
        inventory_ids=[int(item["inventory_id"]) for item in targets],
        idempotency_key=f"auto-activate:{order_id}",
        manual=False,
    )
    with connect() as conn:
        conn.execute(
            "UPDATE fulfillments SET status='activation_queued', updated_at=datetime('now') WHERE order_id=?",
            (order_id,),
        )
    if batch.get("status") == "queued" and get_settings().dry_run:
        from .activation.queue import _manager
        await _manager().process_batch(int(batch["id"]))
    result = get_fulfillment(order_id) or fulfillment
    result["activation_batch"] = get_activation_batch(int(batch["id"]))
    return result


def preview_delivery_text(inventory_ids: list[int] | None = None) -> dict[str, Any]:
    items = []
    for inventory_id in inventory_ids or []:
        item = get_inventory_item(int(inventory_id))
        if item:
            items.append(item)
    if not items:
        items = [{"email": "example@example.com", "password": "password", "primary_token": "token-preview", "session_token": ""}]
    return {"text": render_delivery_text(items)}


async def handle_buyer_message(
    *, order_id: str, buyer_id: str = "", text: str, idempotency_key: str = ""
) -> dict[str, Any]:
    write_audit(
        "xianyu.message.received",
        order_id=order_id,
        idempotency_key=idempotency_key,
        payload={"text": text},
    )
    if not order_id:
        return {"ok": False, "ignored": True, "message": "missing order_id"}
    if is_activation_trigger(text):
        write_audit(
            "xianyu.message.activation_trigger",
            order_id=order_id,
            idempotency_key=idempotency_key,
            payload={"text": text},
        )
        try:
            fulfillment = await activate_order(order_id)
            batch = fulfillment.get("activation_batch") or {}
            return {
                "ok": True,
                "activation_trigger": True,
                "reply_text": f"收到，已进入激活队列，前面还有 {batch.get('ahead_orders', 0)} 单，请稍等。",
                "fulfillment": fulfillment,
            }
        except Exception as exc:
            write_audit("xianyu.message.activation_failed", order_id=order_id, payload={"error": str(exc), "text": text})
            return {
                "ok": False,
                "activation_trigger": True,
                "reply_text": "已收到，我这边正在处理，请稍等。",
                "error": str(exc),
            }
    if is_invite_like_message(text):
        return {"ok": True, "needs_exact_trigger": True, "reply_text": "请直接回复：全部邮箱无误 已邀请"}
    return {"ok": True, "ignored": True}
