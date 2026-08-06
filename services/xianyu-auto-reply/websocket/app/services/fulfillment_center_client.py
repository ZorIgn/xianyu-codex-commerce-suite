from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

import aiohttp
from loguru import logger


_SESSION: aiohttp.ClientSession | None = None
_SESSION_LOOP: asyncio.AbstractEventLoop | None = None


def _load_local_env_once() -> None:
    if os.environ.get("_FULFILLMENT_CENTER_ENV_LOADED") == "1":
        return
    os.environ["_FULFILLMENT_CENTER_ENV_LOADED"] = "1"
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key.startswith("FULFILLMENT_CENTER_") and key not in os.environ:
                os.environ[key] = value
    except Exception as exc:
        logger.warning(f"[fulfillment-center] failed to load local .env: {exc}")


def _enabled() -> bool:
    _load_local_env_once()
    value = os.getenv("FULFILLMENT_CENTER_ENABLED", "true").strip().lower()
    return value not in {"0", "false", "no", "off", "disabled"}


def is_item_enabled(item_id: str) -> bool:
    """Use explicit item opt-in; card binding cardinality is not routing logic."""
    _load_local_env_once()
    if os.getenv("FULFILLMENT_CENTER_ALL_ITEMS", "false").strip().lower() in {"1", "true", "yes", "on"}:
        return bool(str(item_id or "").strip())
    allowed = {
        value.strip()
        for value in os.getenv("FULFILLMENT_CENTER_ITEM_IDS", "").split(",")
        if value.strip()
    }
    return str(item_id or "").strip() in allowed


def _base_url() -> str:
    _load_local_env_once()
    return os.getenv("FULFILLMENT_CENTER_URL", "http://127.0.0.1:8765").rstrip("/")


async def _get_session() -> aiohttp.ClientSession:
    global _SESSION, _SESSION_LOOP
    loop = asyncio.get_running_loop()
    if _SESSION is None or _SESSION.closed or _SESSION_LOOP is not loop:
        if _SESSION is not None and not _SESSION.closed:
            await _SESSION.close()
        timeout = aiohttp.ClientTimeout(
            total=float(os.getenv("FULFILLMENT_CENTER_TIMEOUT", "5")),
            connect=1,
            sock_connect=1,
            sock_read=4,
        )
        _SESSION = aiohttp.ClientSession(
            timeout=timeout,
            connector=aiohttp.TCPConnector(limit=100, limit_per_host=100, ttl_dns_cache=300),
        )
        _SESSION_LOOP = loop
    return _SESSION


async def close_fulfillment_center_session() -> None:
    global _SESSION, _SESSION_LOOP
    if _SESSION is not None and not _SESSION.closed:
        await _SESSION.close()
    _SESSION = None
    _SESSION_LOOP = None


async def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> tuple[int, dict[str, Any], str]:
    last_error = ""
    for attempt in range(3):
        try:
            session = await _get_session()
            async with session.post(url, json=payload, headers=headers) as response:
                body = await response.text()
                try:
                    data = await response.json(content_type=None)
                except Exception:
                    data = {"raw": body}
                if response.status >= 500 and attempt < 2:
                    await asyncio.sleep(0.15 * (attempt + 1))
                    continue
                return response.status, data if isinstance(data, dict) else {"raw": body}, body
        except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as exc:
            last_error = str(exc)
            if attempt < 2:
                await asyncio.sleep(0.15 * (attempt + 1))
                continue
            break
        except Exception as exc:
            last_error = str(exc)
            break
    return 599, {"error": last_error or "fulfillment center request failed"}, last_error


def _failure(status: int, data: dict[str, Any], body: str) -> dict[str, Any]:
    return {
        "handled": True,
        "enabled": True,
        "success": False,
        "status": status,
        "message": str(data.get("message") or data.get("error") or body[:500] or "fulfillment center request failed"),
        "data": data,
    }


async def try_ship_from_fulfillment_center(
    *,
    order_no: str,
    buyer_id: str,
    item_id: str,
    quantity: int = 1,
    platform: str = "chatgpt",
    chat_id: str = "",
    account_id: str = "",
) -> dict[str, Any]:
    """Queue a paid order; the fulfillment worker owns allocation and IM sending."""
    if not _enabled():
        logger.warning("[fulfillment-center] disabled, falling back to built-in card delivery")
        return {"handled": False, "enabled": False}
    if not is_item_enabled(item_id):
        return {"handled": False, "enabled": True, "reason": "item_not_opted_in"}
    order_no = str(order_no or "").strip()
    buyer_id = str(buyer_id or "").strip()
    item_id = str(item_id or "").strip()
    chat_id = str(chat_id or "").strip()
    account_id = str(account_id or "").strip()
    if not order_no or not buyer_id or not item_id or not chat_id or not account_id:
        return {
            "handled": True,
            "enabled": True,
            "success": False,
            "message": "order_id, buyer_id, item_id, chat_id and account_id are required",
        }

    payload = {
        "order_id": order_no,
        "item_id": item_id,
        "buyer_id": buyer_id,
        "chat_id": chat_id,
        "account_id": account_id,
        "platform": platform,
        "quantity": max(1, int(quantity or 1)),
    }
    headers = {"Idempotency-Key": f"xianyu-order-paid-{order_no}"}
    status, data, body = await _post_json(
        f"{_base_url()}/webhooks/xianyu/order-paid",
        payload,
        headers,
    )
    if status >= 400 or data.get("ok") is False or data.get("success") is False or not data.get("queued"):
        logger.error(
            f"[fulfillment-center] order-paid queue rejected: status={status}, order_id={order_no}, body={body[:500]}"
        )
        return _failure(status, data, body)
    logger.info(
        f"[fulfillment-center] order queued: order_id={order_no}, quantity={payload['quantity']}, "
        f"account_id={account_id}, chat_id={chat_id}"
    )
    return {
        "handled": True,
        "enabled": True,
        "success": True,
        "queued": True,
        "data": data,
    }


async def reconcile_fulfillment_quantity(order_no: str, quantity: int) -> dict[str, Any]:
    """Increase a queued/shipped order target; the backend permits top-up after shipped."""
    if not _enabled():
        return {"success": False, "enabled": False, "message": "fulfillment center disabled"}
    order_no = str(order_no or "").strip()
    quantity = max(1, int(quantity or 1))
    if not order_no:
        return {"success": False, "message": "order_id is required"}
    headers = {"Idempotency-Key": f"xianyu-reconcile-{order_no}-{quantity}"}
    status, data, body = await _post_json(
        f"{_base_url()}/delivery/jobs/{quote(order_no, safe='')}/reconcile",
        {"quantity": quantity},
        headers,
    )
    if status >= 400 or data.get("ok") is False or data.get("success") is False:
        logger.warning(
            f"[fulfillment-center] quantity reconcile failed: order_id={order_no}, quantity={quantity}, status={status}"
        )
        return {"success": False, "status": status, "message": str(data.get("message") or body[:500]), "data": data}
    return {"success": True, "status": status, "data": data}
