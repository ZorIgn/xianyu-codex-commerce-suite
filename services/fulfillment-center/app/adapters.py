from __future__ import annotations

from typing import Any

import httpx

from .audit import write_audit
from .config import get_settings
from .settings_store import get_setting


class XianyuAdapter:
    async def send_message(self, buyer_id: str, order_id: str, text: str) -> dict[str, Any]:
        settings = get_settings()
        base_url = get_setting("xianyu_base_url").rstrip("/")
        endpoint = get_setting("xianyu_send_endpoint", "/internal/accounts/{account_id}/send-message") or "/internal/accounts/{account_id}/send-message"
        account_id = get_setting("xianyu_account_id")
        if "{account_id}" in endpoint:
            endpoint = endpoint.replace("{account_id}", account_id)
        token = get_setting("xianyu_api_token")
        if settings.dry_run or not base_url:
            result = {"ok": True, "dry_run": True, "text": text}
            write_audit("xianyu.send_message.dry_run", order_id=order_id, payload=result)
            return result
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{base_url}{endpoint}",
                headers=headers,
                json={"buyer_id": buyer_id, "order_id": order_id, "text": text, "chat_id": buyer_id, "message": text},
            )
            resp.raise_for_status()
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"text": resp.text}
            write_audit("xianyu.send_message", order_id=order_id, payload={"endpoint": endpoint, "response": data})
            return data


class CockpitAdapter:
    async def import_accounts(self, lines: list[str], platform: str = "chatgpt") -> dict[str, Any]:
        settings = get_settings()
        base_url = get_setting("cockpit_base_url").rstrip("/")
        token = get_setting("cockpit_api_token")
        if settings.dry_run or not base_url:
            result = {"ok": True, "dry_run": True, "count": len(lines)}
            write_audit("cockpit.import.dry_run", payload=result)
            return result
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{base_url}/accounts/import",
                headers=headers,
                json={"platform": platform, "lines": lines},
            )
            resp.raise_for_status()
            return resp.json()
