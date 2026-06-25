from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import aiohttp
from loguru import logger


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


def _base_url() -> str:
    _load_local_env_once()
    return os.getenv("FULFILLMENT_CENTER_URL", "http://127.0.0.1:8765").rstrip("/")


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
    """Return external delivery text from the local fulfillment center.

    The fulfillment center owns inventory deduction. Xianyu still owns the
    actual IM send, so send_to_xianyu is false here.
    """
    if not _enabled():
        logger.warning("[fulfillment-center] disabled, falling back to built-in card delivery")
        return {"handled": False, "enabled": False}

    payload = {
        "order_id": order_no,
        "buyer_id": buyer_id or chat_id,
        "item_id": item_id,
        "platform": platform,
        "quantity": max(1, int(quantity or 1)),
        "send_to_xianyu": False,
    }
    headers = {"Idempotency-Key": f"xianyu-ship-{order_no}"}
    url = f"{_base_url()}/fulfillments/ship"
    timeout = aiohttp.ClientTimeout(total=float(os.getenv("FULFILLMENT_CENTER_TIMEOUT", "30")))
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    logger.error(f"[履约中心] 出库失败: status={resp.status}, body={text[:500]}")
                    return {"handled": True, "enabled": True, "success": False, "message": text, "status": resp.status}
                try:
                    data = await resp.json()
                except Exception:
                    data = {"raw": text}
    except Exception as exc:
        logger.error(f"[履约中心] 请求异常: {exc}")
        return {"handled": True, "enabled": True, "success": False, "message": str(exc)}

    delivery_text = str(data.get("delivery_text") or "")
    if not delivery_text:
        logger.error(f"[履约中心] 响应缺少 delivery_text: {data}")
        return {"handled": True, "enabled": True, "success": False, "message": "履约中心响应缺少 delivery_text", "data": data}

    logger.info(
        f"[履约中心] 出库成功: order_no={order_no}, quantity={payload['quantity']}, "
        f"account_id={account_id}, chat_id={chat_id}"
    )
    return {"handled": True, "enabled": True, "success": True, "delivery_text": delivery_text, "data": data}
