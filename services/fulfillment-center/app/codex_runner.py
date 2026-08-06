from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import get_settings
from .settings_store import get_setting


ABAI_PROJECT = get_settings().abai_project_root
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass
class CodexResult:
    ok: bool
    reply: str
    error: str = ""
    switch_result: dict[str, Any] | None = None


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 12:
        return "***"
    return f"{value[:6]}...{value[-4:]}"


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    except Exception:
        return {}


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
        return result
    return {}


def _raw_payload(item: dict[str, Any]) -> dict[str, Any]:
    try:
        raw = json.loads(item.get("source_payload") or "{}")
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _extract_codex_tokens(item: dict[str, Any]) -> dict[str, str]:
    raw = _raw_payload(item)
    credentials = _credentials_dict(raw.get("credentials"))
    merged = {**raw, **credentials}
    access_token = str(item.get("primary_token") or merged.get("access_token") or merged.get("accessToken") or "")
    refresh_token = str(item.get("refresh_token") or merged.get("refresh_token") or merged.get("refreshToken") or "")
    id_token = str(merged.get("id_token") or merged.get("idToken") or "")
    account_id = str(merged.get("account_id") or merged.get("chatgpt_account_id") or "")
    if not account_id:
        for token in (access_token, id_token):
            payload = _decode_jwt_payload(token)
            auth = payload.get("https://api.openai.com/auth", {})
            if isinstance(auth, dict):
                account_id = str(auth.get("chatgpt_account_id") or auth.get("account_id") or "")
                if account_id:
                    break
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "id_token": id_token,
        "account_id": account_id,
    }


def _extract_session_and_cookies(item: dict[str, Any]) -> tuple[str, str]:
    session_token = str(item.get("session_token") or "")
    cookies = str(item.get("cookies") or "")
    raw = _raw_payload(item)
    credentials = _credentials_dict(raw.get("credentials"))
    session_token = session_token or str(raw.get("session_token") or raw.get("sessionToken") or credentials.get("session_token") or credentials.get("sessionToken") or "")
    cookies = cookies or str(raw.get("cookies") or raw.get("cookie") or credentials.get("cookies") or credentials.get("cookie") or "")
    return session_token, cookies


def _switch_codex_desktop_account(item: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    session_token, cookies = _extract_session_and_cookies(item)
    if not session_token and "__Secure-next-auth.session-token" not in cookies:
        return False, {"skipped": True, "reason": "missing_session_token_or_cookies"}
    if str(ABAI_PROJECT) not in sys.path:
        sys.path.insert(0, str(ABAI_PROJECT))
    try:
        from platforms.chatgpt.switch import close_codex_app, switch_codex_account

        close_codex_app()
        ok, result = switch_codex_account(session_token=session_token, cookies=cookies)
        return bool(ok), result if isinstance(result, dict) else {"result": result}
    except Exception as exc:
        return False, {"error": f"调用 aBai/Cockpit Codex 桌面切号失败: {exc}"}


def _write_codex_home(item: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    tokens = _extract_codex_tokens(item)
    if not tokens["access_token"] or not tokens["refresh_token"]:
        return False, {
            "error": "库存缺少 Codex CLI 需要的 access_token/refresh_token",
            "present": {k: bool(v) for k, v in tokens.items()},
        }
    inventory_id = str(item.get("id") or tokens["account_id"] or item.get("email") or "unknown")
    home = DATA_DIR / "codex_homes" / inventory_id
    home.mkdir(parents=True, exist_ok=True)
    auth_path = home / "auth.json"
    auth_payload = {
        "OPENAI_API_KEY": None,
        "last_refresh": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tokens": {
            "access_token": tokens["access_token"],
            "account_id": tokens["account_id"],
            "id_token": tokens["id_token"],
            "refresh_token": tokens["refresh_token"],
        },
    }
    auth_path.write_text(json.dumps(auth_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return True, {
        "method": "codex_cli_auth_json",
        "codex_home": str(home),
        "auth_path": str(auth_path),
        "email": item.get("email", ""),
        "account_id": tokens["account_id"],
        "token_preview": _mask_secret(tokens["access_token"]),
    }


async def run_codex_activation(item: dict[str, Any]) -> CodexResult:
    settings = get_settings()
    prompt = get_setting("codex_prompt", "你好") or "你好"
    command = get_setting("codex_command", settings.codex_command) or settings.codex_command
    if settings.dry_run:
        return CodexResult(ok=True, reply="Codex dry-run: 已模拟发送你好", switch_result={"dry_run": True})

    cli_ready, cli_result = _write_codex_home(item)
    desktop_ok, desktop_result = _switch_codex_desktop_account(item)
    switch_result = {"cli": cli_result, "desktop": desktop_result, "desktop_ok": desktop_ok}
    if not cli_ready:
        return CodexResult(ok=False, reply="", error=str(cli_result.get("error") or cli_result), switch_result=switch_result)

    env = os.environ.copy()
    env["CODEX_HOME"] = str(cli_result["codex_home"])
    last_message_path = Path(cli_result["codex_home"]) / "last_message.txt"
    if last_message_path.exists():
        last_message_path.unlink()
    args = [
        "cmd.exe",
        "/c",
        command,
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--cd",
        str(DATA_DIR),
        "--output-last-message",
        str(last_message_path),
        prompt,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=settings.codex_timeout_seconds)
    except asyncio.TimeoutError:
        return CodexResult(ok=False, reply="", error="codex timeout", switch_result=switch_result)
    except FileNotFoundError:
        return CodexResult(ok=False, reply="", error=f"codex command not found: {command}", switch_result=switch_result)

    out = stdout.decode("utf-8", errors="replace").strip()
    if last_message_path.exists():
        final_text = last_message_path.read_text(encoding="utf-8", errors="replace").strip()
        if final_text:
            out = final_text
    err = stderr.decode("utf-8", errors="replace").strip()
    switch_result["command"] = " ".join(args)
    switch_result["returncode"] = proc.returncode
    switch_result["stderr_preview"] = err[-1000:]
    if proc.returncode != 0:
        return CodexResult(ok=False, reply=out[-2000:], error=err or f"exit {proc.returncode}", switch_result=switch_result)
    return CodexResult(ok=True, reply=out or "ok", switch_result=switch_result)


async def run_codex_hello() -> CodexResult:
    return CodexResult(ok=False, reply="", error="run_codex_hello 已废弃，请使用 run_codex_activation(item)")



