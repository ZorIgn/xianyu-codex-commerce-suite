from __future__ import annotations

import base64
import hashlib
import json
import random
import secrets
import subprocess
import threading
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .audit import redact_text, write_audit
from .config import get_settings
from .db import connect
from .settings_store import get_setting


CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_AUTH_URL = "https://auth.openai.com/oauth/authorize"
CODEX_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_REDIRECT_URI = "http://localhost:1455/auth/callback"
CODEX_SCOPE = "openid email profile offline_access"
SESSION_TTL_MINUTES = 15
AUTO_RESULT_PREFIX = "__COCKPIT_OAUTH_RESULT__"
_oauth_browser_lock = threading.Lock()
_oauth_browser_state_lock = threading.Lock()
_oauth_browser_state: dict[str, Any] = {
    "running": False,
    "inventory_id": None,
    "email": "",
    "started_at": "",
}


def oauth_reauth_status() -> dict[str, Any]:
    with _oauth_browser_state_lock:
        return dict(_oauth_browser_state)


class OAuthReauthError(RuntimeError):
    pass


class OAuthRefreshRequired(OAuthReauthError):
    pass


@dataclass(frozen=True)
class OAuthStart:
    auth_url: str
    state: str
    code_verifier: str
    redirect_uri: str
    client_id: str


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _jwt_claims(token: str) -> dict[str, Any]:
    try:
        parts = str(token or "").split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except Exception:
        return {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_callback(callback_url: str) -> dict[str, str]:
    candidate = (callback_url or "").strip()
    if not candidate:
        return {"code": "", "state": "", "error": "", "error_description": ""}
    if "://" not in candidate:
        candidate = f"http://localhost/?{candidate.lstrip('?')}"
    parsed = urllib.parse.urlparse(candidate)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    fragment = urllib.parse.parse_qs(parsed.fragment, keep_blank_values=True)
    for key, values in fragment.items():
        query.setdefault(key, values)
    return {
        key: str((query.get(key) or [""])[0] or "").strip()
        for key in ("code", "state", "error", "error_description")
    }


def _token_client_id(row: dict[str, Any]) -> str:
    source = {}
    try:
        source = json.loads(str(row.get("source_payload") or "{}"))
    except Exception:
        pass
    access_token = str(row.get("primary_token") or "")
    id_token = str(source.get("id_token") or source.get("idToken") or "")
    for token in (access_token, id_token):
        claims = _jwt_claims(token)
        candidate = str(
            claims.get("client_id")
            or (claims.get("https://api.openai.com/auth") or {}).get("client_id")
            or ""
        ).strip()
        if candidate:
            return candidate
    return CODEX_CLIENT_ID


def _token_email(payload: dict[str, Any]) -> str:
    for token_key in ("id_token", "access_token"):
        claims = _jwt_claims(str(payload.get(token_key) or ""))
        profile = claims.get("https://api.openai.com/profile")
        if isinstance(profile, dict) and profile.get("email"):
            return str(profile["email"]).strip().lower()
        if claims.get("email"):
            return str(claims["email"]).strip().lower()
    return ""


def _token_account_id(payload: dict[str, Any]) -> str:
    for key in ("account_id", "chatgpt_account_id"):
        if payload.get(key):
            return str(payload[key]).strip()
    for token_key in ("access_token", "id_token"):
        claims = _jwt_claims(str(payload.get(token_key) or ""))
        auth = claims.get("https://api.openai.com/auth")
        if isinstance(auth, dict):
            for key in ("chatgpt_account_id", "account_id"):
                if auth.get(key):
                    return str(auth[key]).strip()
        if claims.get("account_id"):
            return str(claims["account_id"]).strip()
    return ""


def start_oauth(row: dict[str, Any]) -> OAuthStart:
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    client_id = _token_client_id(row)
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": CODEX_REDIRECT_URI,
        "scope": CODEX_SCOPE,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "prompt": "login",
    }
    return OAuthStart(
        auth_url=f"{CODEX_AUTH_URL}?{urllib.parse.urlencode(params)}",
        state=state,
        code_verifier=verifier,
        redirect_uri=CODEX_REDIRECT_URI,
        client_id=client_id,
    )


def create_reauth_session(inventory_id: int) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM inventory_items WHERE id = ?", (int(inventory_id),)
        ).fetchone()
        if row is None:
            raise KeyError(f"库存不存在: {inventory_id}")
        item = dict(row)
    start = start_oauth(item)
    session_id = secrets.token_urlsafe(18)
    expires_at = _iso(_now() + timedelta(minutes=SESSION_TTL_MINUTES))
    with connect() as conn:
        conn.execute(
            """
            UPDATE oauth_reauth_sessions
            SET status = 'superseded', error = 'replaced by a newer session'
            WHERE inventory_id = ? AND status = 'pending'
            """,
            (int(inventory_id),),
        )
        conn.execute(
            """
            INSERT INTO oauth_reauth_sessions(
                id, inventory_id, status, state, code_verifier,
                client_id, redirect_uri, auth_url, expires_at
            ) VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                int(inventory_id),
                start.state,
                start.code_verifier,
                start.client_id,
                start.redirect_uri,
                start.auth_url,
                expires_at,
            ),
        )
    write_audit(
        "inventory.oauth_reauth_started",
        inventory_id=int(inventory_id),
        payload={"session_id": session_id, "email": item.get("email", "")},
    )
    return {
        "session_id": session_id,
        "email": item.get("email", ""),
        "auth_url": start.auth_url,
        "expires_at": expires_at,
        "mailbox_url": "https://app.wyx66.com/",
    }


def _merge_source(row: dict[str, Any], token_payload: dict[str, Any]) -> str:
    try:
        source = json.loads(str(row.get("source_payload") or "{}"))
    except Exception:
        source = {}
    if not isinstance(source, dict):
        source = {}
    source.update(
        {
            key: value
            for key, value in token_payload.items()
            if value not in (None, "")
        }
    )
    credentials = source.get("credentials")
    if not isinstance(credentials, dict):
        credentials = {}
    credentials.update(
        {
            key: value
            for key, value in token_payload.items()
            if value not in (None, "")
        }
    )
    source["credentials"] = credentials
    return json.dumps(source, ensure_ascii=False)


def _replace_credentials(inventory_id: int, token_payload: dict[str, Any]) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM inventory_items WHERE id = ?", (int(inventory_id),)
        ).fetchone()
        if row is None:
            raise KeyError(f"库存不存在: {inventory_id}")
        current = dict(row)
        access_token = str(token_payload.get("access_token") or "").strip()
        refresh_token = str(
            token_payload.get("refresh_token") or current.get("refresh_token") or ""
        ).strip()
        id_token = str(token_payload.get("id_token") or "").strip()
        if not access_token or not refresh_token:
            raise OAuthReauthError("OAuth 返回缺少 access_token 或 refresh_token")
        payload = {
            **token_payload,
            "email": current.get("email", ""),
            "account_id": _token_account_id(token_payload)
            or str(current.get("account_id") or ""),
        }
        source_payload = _merge_source(current, payload)
        conn.execute(
            """
            UPDATE inventory_items
            SET primary_token = ?, refresh_token = ?, source_payload = ?,
                activation_error = '', updated_at = datetime('now')
            WHERE id = ?
            """,
            (access_token, refresh_token, source_payload, int(inventory_id)),
        )
    write_audit(
        "inventory.oauth_credentials_updated",
        inventory_id=int(inventory_id),
        payload={"email": current.get("email", ""), "method": token_payload.get("method", "oauth")},
    )
    return {
        "id": int(inventory_id),
        "email": current.get("email", ""),
        "updated": True,
        "oauth_ready": bool(access_token and refresh_token and id_token),
    }


async def refresh_inventory_oauth(inventory_id: int) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM inventory_items WHERE id = ?", (int(inventory_id),)
        ).fetchone()
        if row is None:
            raise KeyError(f"库存不存在: {inventory_id}")
        item = dict(row)
    refresh_token = str(item.get("refresh_token") or "").strip()
    if not refresh_token:
        raise OAuthRefreshRequired("库存没有 refresh_token，需要重新授权")
    client_id = _token_client_id(item)
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                CODEX_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                },
                headers={"Accept": "application/json"},
            )
        data = response.json() if response.content else {}
        if response.status_code >= 400 or not isinstance(data, dict):
            detail = data.get("error_description") or data.get("error") or response.status_code
            raise OAuthRefreshRequired(f"refresh token 已失效或被拒绝: {detail}")
        payload = {
            "access_token": data.get("access_token", ""),
            "refresh_token": data.get("refresh_token", refresh_token),
            "id_token": data.get("id_token", ""),
            "expires_at": data.get("expires_at", ""),
            "expires_in": data.get("expires_in", ""),
            "method": "refresh_token",
        }
        result = _replace_credentials(inventory_id, payload)
        result["method"] = "refresh_token"
        result["oauth_ready"] = bool(
            result.get("oauth_ready")
            or (payload.get("access_token") and payload.get("refresh_token"))
        )
        return result
    except OAuthRefreshRequired:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise OAuthRefreshRequired(f"刷新 OAuth 失败，需要重新授权: {exc}") from exc


async def exchange_callback(session_id: str, callback_url: str) -> dict[str, Any]:
    params = _parse_callback(callback_url)
    if params["error"]:
        raise OAuthReauthError(params["error_description"] or params["error"])
    if not params["code"] or not params["state"]:
        raise OAuthReauthError("回调 URL 缺少 code 或 state")
    with connect() as conn:
        row = conn.execute(
            """
            SELECT s.*, i.email
            FROM oauth_reauth_sessions s
            JOIN inventory_items i ON i.id = s.inventory_id
            WHERE s.id = ? AND s.status = 'pending'
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            raise OAuthReauthError("授权会话不存在、已完成或已失效")
        session = dict(row)
    if session["state"] != params["state"]:
        raise OAuthReauthError("OAuth state 校验失败")
    if datetime.fromisoformat(session["expires_at"]) <= _now():
        raise OAuthReauthError("授权会话已过期，请重新开始")
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            CODEX_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": params["code"],
                "redirect_uri": session["redirect_uri"],
                "client_id": session["client_id"],
                "code_verifier": session["code_verifier"],
            },
            headers={"Accept": "application/json"},
        )
    data = response.json() if response.content else {}
    if response.status_code >= 400 or not isinstance(data, dict):
        detail = data.get("error_description") or data.get("error") or response.status_code
        raise OAuthReauthError(f"OAuth token 交换失败: {detail}")
    token_email = _token_email(data)
    expected_email = str(session["email"] or "").strip().lower()
    if token_email and expected_email and token_email != expected_email:
        raise OAuthReauthError("授权后的邮箱与当前库存邮箱不一致，已拒绝覆盖")
    result = _replace_credentials(
        int(session["inventory_id"]),
        {
            **data,
            "method": "authorization_code",
        },
    )
    with connect() as conn:
        conn.execute(
            """
            UPDATE oauth_reauth_sessions
            SET status = 'completed', completed_at = datetime('now'), error = ''
            WHERE id = ?
            """,
            (session_id,),
        )
    result["method"] = "authorization_code"
    return result


def import_oauth_payload(inventory_id: int, payload: Any) -> dict[str, Any]:
    items = payload if isinstance(payload, list) else [payload]
    if isinstance(payload, dict):
        for key in ("accounts", "items", "data"):
            if isinstance(payload.get(key), list):
                items = payload[key]
                break
    candidates = [item for item in items if isinstance(item, dict)]
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM inventory_items WHERE id = ?", (int(inventory_id),)
        ).fetchone()
    if row is None:
        raise KeyError(f"库存不存在: {inventory_id}")
    expected = str(row["email"] or "").strip().lower()
    for raw in candidates:
        credentials = raw.get("credentials") if isinstance(raw.get("credentials"), dict) else {}
        merged = {**raw, **credentials}
        email = str(merged.get("email") or merged.get("name") or "").strip().lower()
        if email != expected:
            continue
        payload = {
            "access_token": merged.get("access_token") or merged.get("accessToken"),
            "refresh_token": merged.get("refresh_token") or merged.get("refreshToken"),
            "id_token": merged.get("id_token") or merged.get("idToken"),
            "account_id": merged.get("account_id") or merged.get("chatgpt_account_id"),
            "expires_at": merged.get("expires_at") or merged.get("expired"),
            "method": "cockpit_export",
        }
        return _replace_credentials(inventory_id, payload)
    raise OAuthReauthError("文件中没有与当前库存邮箱匹配的 OAuth 账号")

def automatic_reauthorize_inventory_oauth(inventory_id: int) -> dict[str, Any]:
    """Run the local Cockpit OAuth browser flow and persist its token result.

    The worker reads the configured local mailbox provider from the existing
    aBai/Cockpit installation. No mailbox refresh token is sent to a new
    external service from this project.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM inventory_items WHERE id = ?", (int(inventory_id),)
        ).fetchone()
        if row is None:
            raise KeyError(f"库存不存在: {inventory_id}")
        item = dict(row)

    settings = get_settings()
    worker_script = Path(__file__).with_name("cockpit_oauth_worker.py")
    if not worker_script.exists():
        raise OAuthReauthError("本地 Cockpit OAuth worker 不存在")
    if not settings.cockpit_python.exists():
        raise OAuthReauthError(
            f"Cockpit Python 不存在: {settings.cockpit_python}"
        )
    if not _oauth_browser_lock.acquire(blocking=False):
        with _oauth_browser_state_lock:
            current = dict(_oauth_browser_state)
        if current.get("running"):
            raise OAuthReauthError(
                "已有 OAuth 自动授权任务正在执行："
                f"库存 #{current.get('inventory_id')} {current.get('email')}，"
                f"开始于 {current.get('started_at')}"
            )
        raise OAuthReauthError("已有一个 OAuth 自动授权任务正在执行，请等待它完成")

    with _oauth_browser_state_lock:
        _oauth_browser_state.update({"running": True, "inventory_id": int(inventory_id),
            "email": str(item.get("email") or ""), "started_at": _iso(_now())})

    process = None
    try:
        request_payload = {
            "email": str(item.get("email") or ""),
            "password": str(item.get("password") or ""),
            "abai_project_root": str(settings.abai_project_root),
            "browser_mode": settings.oauth_browser_mode,
        }
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        process = subprocess.Popen(
            [
                str(settings.cockpit_python),
                str(worker_script),
            ],
            cwd=str(settings.abai_project_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
        try:
            stdout, stderr_text = process.communicate(
                json.dumps(request_payload, ensure_ascii=False),
                timeout=max(60, int(settings.oauth_browser_timeout_seconds)),
            )
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.communicate()
            raise OAuthReauthError("Cockpit OAuth 自动授权超时") from exc
    except OSError as exc:
        raise OAuthReauthError(f"启动 Cockpit OAuth worker 失败: {exc}") from exc
    finally:
        _oauth_browser_lock.release()
        with _oauth_browser_state_lock:
            _oauth_browser_state.update({"running": False, "inventory_id": None,
                "email": "", "started_at": ""})

    result_payload: dict[str, Any] = {}
    for line in str(stdout or "").splitlines():
        if not line.startswith(AUTO_RESULT_PREFIX):
            continue
        try:
            parsed = json.loads(line[len(AUTO_RESULT_PREFIX):])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            result_payload = parsed

    if not result_payload.get("ok"):
        message = redact_text(result_payload.get("error") or "Cockpit OAuth 自动授权失败")
        stderr_preview = redact_text(stderr_text, 1200).strip()
        if stderr_preview and message == "Cockpit OAuth 自动授权失败":
            message += "；worker 日志：" + stderr_preview
        write_audit(
            "inventory.oauth_reauth_failed",
            inventory_id=int(inventory_id),
            payload={"error": message[:2000]},
        )
        raise OAuthReauthError(message)

    token_payload = {
        key: value
        for key, value in result_payload.items()
        if key not in {"ok", "error"}
    }
    result = _replace_credentials(
        inventory_id,
        {
            **token_payload,
            "method": "cockpit_local_auto_oauth",
        },
    )
    result["method"] = "cockpit_local_auto_oauth"
    return result

def _reauth_error_retryable(exc: Exception) -> bool:
    if isinstance(exc, KeyError):
        return False
    text = str(exc or "").lower()
    terminal_markers = (
        "invalid password",
        "incorrect password",
        "password incorrect",
        "wrong password",
        "密码错误",
        "密码不正确",
        "password is required",
        "missing password",
        "missing credentials",
        "缺少",
        "库存不存在",
        "inventory not found",
        "mfa",
        "otp",
        "email_otp",
        "验证码",
        "人工验证",
        "manual verification",
        "需要人工",
    )
    return not any(marker in text for marker in terminal_markers)


def _reauth_retry_delay(attempt: int) -> float:
    raw = get_setting("oauth_reauth_retry_delays", "2,5,10")
    values: list[float] = []
    for value in str(raw).split(","):
        try:
            values.append(max(0.0, float(value.strip())))
        except (TypeError, ValueError):
            continue
    if not values:
        values = [2.0, 5.0, 10.0]
    return values[min(max(0, attempt - 1), len(values) - 1)] + random.uniform(0.0, 0.25)


def automatic_reauthorize_inventory_oauth_retry(
    inventory_id: int,
    *,
    priority: bool = False,
) -> dict[str, Any]:
    """Run local OAuth with bounded, classified retries.

    Activation-before-reauth passes priority=True; the browser is still single
    concurrency, but transient lock contention is retried instead of surfacing
    as an immediate user-facing failure.
    """
    settings = get_settings()
    attempts = max(1, int(settings.oauth_reauth_retry_limit))
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return automatic_reauthorize_inventory_oauth(inventory_id)
        except KeyError:
            raise
        except Exception as exc:
            last_error = exc
            if not _reauth_error_retryable(exc):
                raise OAuthReauthError(redact_text(exc)) from exc
            if attempt >= attempts:
                break
            write_audit(
                "inventory.oauth_reauth_retry",
                inventory_id=int(inventory_id),
                payload={
                    "attempt": attempt,
                    "max_attempts": attempts,
                    "priority": bool(priority),
                    "error": redact_text(exc, 1000),
                },
            )
            time.sleep(_reauth_retry_delay(attempt))
    raise OAuthReauthError(
        redact_text(
            f"OAuth reauthorization failed after {attempts} attempts: "
            f"{last_error or 'unknown error'}"
        )
    )
