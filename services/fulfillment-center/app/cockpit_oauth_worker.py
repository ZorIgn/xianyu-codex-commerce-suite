from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


RESULT_PREFIX = "__COCKPIT_OAUTH_RESULT__"


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_configure_stdio()


def _log(message: str) -> None:
    print(str(message), file=sys.stderr, flush=True)


def _safe_result(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "email",
        "access_token",
        "refresh_token",
        "id_token",
        "account_id",
        "expired",
        "expires_at",
        "last_refresh",
        "type",
    )
    return {key: payload.get(key, "") for key in allowed if payload.get(key) not in (None, "")}


def _keep_password_login(page, log, *, context: str):
    """Keep the OAuth flow on the password path; never choose passwordless OTP."""
    return False

def _lookup_password_from_cockpit(email: str) -> str:
    try:
        from domain.accounts import AccountQuery
        from infrastructure.accounts_repository import AccountsRepository

        _total, records = AccountsRepository().list(
            AccountQuery(platform="chatgpt", email=email, page=1, page_size=5)
        )
        for record in records:
            if str(record.email or "").strip().lower() == email.lower():
                return str(record.password or "")
    except Exception as exc:
        _log(f"未能从 Cockpit 读取原账号密码，继续使用库存字段: {exc}")
    return ""

def run(payload: dict[str, Any]) -> dict[str, Any]:
    diagnostics: list[str] = []
    project_root = Path(
        payload.get("abai_project_root")
        or os.environ.get("ABAI_PROJECT_ROOT")
        or Path(__file__).resolve().parents[1].parent / "aBaiAutoplus_syunnrai"
    ).resolve()
    if not project_root.exists():
        raise RuntimeError(f"Cockpit/aBai 项目目录不存在: {project_root}")
    sys.path.insert(0, str(project_root))

    email = str(payload.get("email") or "").strip()
    password = str(payload.get("password") or "")
    if not password:
        password = _lookup_password_from_cockpit(email)
    if not email:
        raise RuntimeError("OAuth 缺少邮箱地址")
    if not password:
        raise RuntimeError("库存未保存账号密码，密码模式无法重新授权，请重新导入包含 password 的 JSON")

    from platforms._browser_backend import parse_checkout_mode
    import platforms.chatgpt.browser_register as browser_register_module

    # The shared registration flow prefers passwordless OTP after email.
    # For inventory reauthorization, keep the explicit password path instead.
    browser_register_module._click_passwordless_login_if_available = _keep_password_login
    ChatGPTBrowserRegister = browser_register_module.ChatGPTBrowserRegister

    mode = str(payload.get("browser_mode") or "camoufox_headless")
    backend_config = parse_checkout_mode(mode)
    def log(message: str) -> None:
        text = str(message)
        if "授权链接" not in text and "state=" not in text:
            diagnostics.append(text)
        _log(text)

    log("密码优先 OAuth：不读取邮箱验证码，不使用邮箱 provider")
    register = ChatGPTBrowserRegister(
        headless=backend_config.is_headless,
        proxy=str(payload.get("proxy") or "") or None,
        otp_callback=None,
        log_fn=log,
        backend_config=backend_config,
    )
    log(f"启动 Cockpit Codex OAuth：{email}")
    result = register._retry_oauth_fresh_browser(email, password)
    if not isinstance(result, dict) or not result.get("access_token") or not result.get("refresh_token"):
        detail = "；".join(diagnostics[-8:])
        suffix = ("；运行日志：" + detail[-1600:]) if detail else ""
        raise RuntimeError("Cockpit OAuth 未返回完整 access_token/refresh_token" + suffix)
    return _safe_result(result)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        result = run(payload if isinstance(payload, dict) else {})
        print(RESULT_PREFIX + json.dumps({"ok": True, **result}, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        message = str(exc)
        if "otp" in message.lower() or "验证码" in message:
            message = "此账号需要验证码，密码模式不会跳过验证：" + message
        _log(f"Cockpit OAuth 失败: {message}")
        print(RESULT_PREFIX + json.dumps({"ok": False, "error": message}, ensure_ascii=False), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
