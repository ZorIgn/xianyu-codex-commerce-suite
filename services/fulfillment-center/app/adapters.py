from __future__ import annotations

from typing import Any

import httpx

from .audit import write_audit
from .config import get_settings
from .settings_store import get_setting


class XianyuAdapter:
    async def send_message(
        self,
        buyer_id: str,
        order_id: str,
        text: str,
        *,
        chat_id: str = "",
        account_id: str = "",
    ) -> dict[str, Any]:
        settings = get_settings()
        base_url = get_setting("xianyu_base_url").rstrip("/")
        endpoint = (
            get_setting("xianyu_send_endpoint", "/internal/accounts/{account_id}/send-message")
            or "/internal/accounts/{account_id}/send-message"
        )
        resolved_account_id = str(account_id or get_setting("xianyu_account_id") or "").strip()
        if "{account_id}" in endpoint:
            endpoint = endpoint.replace("{account_id}", resolved_account_id)
        token = get_setting("xianyu_api_token")
        payload = {
            "account_id": resolved_account_id,
            "buyer_id": str(buyer_id or ""),
            "order_id": str(order_id or ""),
            "chat_id": str(chat_id or buyer_id or ""),
            "message": str(text or ""),
            "text": str(text or ""),
            "wait_result": True,
        }
        if settings.dry_run or not base_url:
            result = {"ok": True, "success": True, "code": 200, "dry_run": True, "text": text}
            write_audit("xianyu.send_message.dry_run", order_id=order_id, payload=result)
            return result
        if not resolved_account_id:
            raise RuntimeError("xianyu account_id is required for internal message delivery")
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{base_url}{endpoint}", headers=headers, json=payload)
            resp.raise_for_status()
            data = (
                resp.json()
                if resp.headers.get("content-type", "").startswith("application/json")
                else {"raw": resp.text}
            )
        if not isinstance(data, dict):
            raise RuntimeError("Xianyu internal send returned a non-object JSON response")
        code = data.get("code")
        if data.get("success") is False or (
            code is not None and str(code) not in {"0", "200"}
        ):
            raise RuntimeError(
                f"Xianyu internal send rejected: code={code!r}, message={data.get('message') or data.get('error_message') or 'unknown'}"
            )
        if data.get("success") is not True and code not in (0, 200, "0", "200"):
            raise RuntimeError("Xianyu internal send response did not confirm success")
        send_data = data.get("data")
        if isinstance(send_data, dict) and send_data.get("send_status") == "failed":
            raise RuntimeError(
                f"Xianyu internal send failed: {send_data.get('send_fail_reason') or 'unknown'}"
            )
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
