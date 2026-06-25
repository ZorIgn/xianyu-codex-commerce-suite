from __future__ import annotations

from typing import Any
import re

from .adapters import XianyuAdapter
from .audit import write_audit
from .codex_runner import run_codex_activation
from .db import connect
from .idempotency import remember, seen
from .inventory import (
    get_inventory_item,
    mark_activated,
    mark_activation_failed,
    render_delivery_text,
    reserve_many,
)


STATUS_DONE = {"account_sent", "partially_activated", "activated", "failed"}


def _compact_message_text(text: str) -> str:
    return "".join(ch for ch in (text or "").lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def is_activation_trigger(text: str) -> bool:
    return "全部邮箱无误已邀请" in _compact_message_text(text)


def is_invite_like_message(text: str) -> bool:
    normalized = _compact_message_text(text)
    if is_activation_trigger(text):
        return True
    return any(kw in normalized for kw in (
        "已邀请", "邀请了", "邀了", "发邀请", "发送邀请", "发送了",
        "发了", "弄好了", "好了", "ok", "okay", "完成了", "可以了"
    ))


def get_fulfillment(order_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM fulfillments WHERE order_id = ?", (order_id,)).fetchone()
        if not row:
            return None
        items = conn.execute(
            """
            SELECT fi.*, ii.email, ii.status AS inventory_status, ii.activated_at, ii.activation_error AS inventory_activation_error
            FROM fulfillment_items fi
            JOIN inventory_items ii ON ii.id = fi.inventory_id
            WHERE fi.order_id = ?
            ORDER BY fi.id ASC
            """,
            (order_id,),
        ).fetchall()
    data = dict(row)
    data["items"] = [dict(item) for item in items]
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
    item_id: str,
    quantity: int,
    status: str,
    delivery_text: str = "",
    error: str = "",
) -> dict[str, Any]:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO fulfillments(order_id, buyer_id, item_id, quantity, status, delivery_text, last_error, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(order_id) DO UPDATE SET
                buyer_id = excluded.buyer_id,
                item_id = excluded.item_id,
                quantity = excluded.quantity,
                status = excluded.status,
                delivery_text = excluded.delivery_text,
                last_error = excluded.last_error,
                updated_at = datetime('now')
            """,
            (order_id, buyer_id, item_id, quantity, status, delivery_text, error),
        )
        row = conn.execute("SELECT * FROM fulfillments WHERE order_id = ?", (order_id,)).fetchone()
    return dict(row)


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
    cache = seen(idempotency_key)
    if cache:
        return {"idempotent": True, **cache}

    quantity = max(1, int(quantity or 1))
    try:
        items = reserve_many(order_id, quantity, platform=platform)
        delivery_text = render_delivery_text(items)
        _save_fulfillment(
            order_id=order_id,
            buyer_id=buyer_id,
            item_id=item_id,
            quantity=quantity,
            status="account_sent",
            delivery_text=delivery_text,
        )
        with connect() as conn:
            for item in items:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO fulfillment_items(order_id, inventory_id, status)
                    VALUES (?, ?, 'shipped')
                    """,
                    (order_id, item["id"]),
                )
        if send_to_xianyu:
            await XianyuAdapter().send_message(buyer_id, order_id, delivery_text)
        result = get_fulfillment(order_id) or {}
        write_audit("fulfillment.ship_order", order_id=order_id, idempotency_key=idempotency_key, payload={"quantity": quantity, "send_to_xianyu": send_to_xianyu})
    except Exception as exc:
        result = _save_fulfillment(
            order_id=order_id,
            buyer_id=buyer_id,
            item_id=item_id,
            quantity=quantity,
            status="failed",
            error=str(exc),
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
    idempotency_key: str = "",
) -> dict[str, Any]:
    return await ship_order(
        order_id=order_id,
        buyer_id=buyer_id,
        item_id=item_id,
        quantity=quantity,
        platform=platform,
        send_to_xianyu=True,
        idempotency_key=idempotency_key,
    )


async def activate_inventory_item(order_id: str, inventory_id: int) -> dict[str, Any]:
    order_id = (order_id or "").strip() or f"manual-activate-{inventory_id}"
    item = get_inventory_item(inventory_id)
    if not item:
        raise RuntimeError(f"库存不存在: {inventory_id}")

    existing_order = item.get("reserved_order_id") or ""
    if existing_order:
        order_id = existing_order

    fulfillment = get_fulfillment(order_id)
    if not fulfillment:
        delivery_text = render_delivery_text([item])
        _save_fulfillment(
            order_id=order_id,
            buyer_id="manual",
            item_id="manual",
            quantity=1,
            status="account_sent",
            delivery_text=delivery_text,
        )
        with connect() as conn:
            conn.execute(
                """
                UPDATE inventory_items
                SET status = 'shipped', reserved_order_id = ?, shipped_at = COALESCE(shipped_at, datetime('now')), updated_at = datetime('now')
                WHERE id = ? AND status = 'available'
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
        item = get_inventory_item(inventory_id) or item
    else:
        with connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO fulfillment_items(order_id, inventory_id, status)
                VALUES (?, ?, 'shipped')
                """,
                (order_id, inventory_id),
            )

    write_audit("fulfillment.activate.start", order_id=order_id, inventory_id=inventory_id)
    result = await run_codex_activation(item)
    if result.ok:
        mark_activated(inventory_id, order_id, result.reply)
    else:
        mark_activation_failed(inventory_id, order_id, result.error)

    updated = get_fulfillment(order_id) or {}
    item_statuses = [x.get("status") for x in updated.get("items", [])]
    if item_statuses and all(status == "activated" for status in item_statuses):
        status = "activated"
    elif any(status == "activated" for status in item_statuses):
        status = "partially_activated"
    else:
        status = "account_sent"
    with connect() as conn:
        conn.execute(
            "UPDATE fulfillments SET status = ?, codex_reply = ?, last_error = ?, updated_at = datetime('now') WHERE order_id = ?",
            (status, result.reply, result.error, order_id),
        )
    return get_fulfillment(order_id) or {}


async def activate_order(order_id: str) -> dict[str, Any]:
    fulfillment = get_fulfillment(order_id)
    if not fulfillment:
        raise RuntimeError(f"订单不存在: {order_id}")
    targets = [item for item in fulfillment.get("items", []) if item.get("status") in {"shipped", "activation_failed"}]
    if not targets:
        return fulfillment
    current: dict[str, Any] = fulfillment
    for target in targets:
        current = await activate_inventory_item(order_id, int(target["inventory_id"]))
    return current


def preview_delivery_text(inventory_ids: list[int] | None = None) -> dict[str, Any]:
    items = []
    for inventory_id in inventory_ids or []:
        item = get_inventory_item(int(inventory_id))
        if item:
            items.append(item)
    if not items:
        items = [
            {"email": "example@example.com", "password": "password", "primary_token": "token-preview", "session_token": ""}
        ]
    return {"text": render_delivery_text(items)}


async def handle_buyer_message(*, order_id: str, buyer_id: str = "", text: str, idempotency_key: str = "") -> dict[str, Any]:
    write_audit("xianyu.message.received", order_id=order_id, idempotency_key=idempotency_key, payload={"text": text})
    if not order_id:
        return {"ok": False, "ignored": True, "message": "missing order_id"}

    if is_activation_trigger(text):
        write_audit("xianyu.message.activation_trigger", order_id=order_id, idempotency_key=idempotency_key, payload={"text": text})
        try:
            fulfillment = await activate_order(order_id)
            return {
                "ok": True,
                "activation_trigger": True,
                "reply_text": "收到，正在为您激活，请稍等。",
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
        return {
            "ok": True,
            "needs_exact_trigger": True,
            "reply_text": "请直接回复：全部邮箱无误 已邀请",
        }

    return {"ok": True, "ignored": True}
