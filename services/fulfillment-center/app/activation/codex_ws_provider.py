from __future__ import annotations

import asyncio
import json
import random
import time
import uuid
from typing import Any, Callable

import httpx
import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatus

from ..audit import write_audit
from ..config import get_settings
from ..settings_store import get_setting
from .base_provider import result_dict
from .desktop_provider import _extract_oauth_tokens

# 与已安装的 codex-cli 0.140.0 对齐：Codex 后端 Responses API 的 WebSocket 传输。
# 参考 codex-rs（openai/codex）:
#   - 端点: wss://chatgpt.com/backend-api/codex/responses
#   - 握手头: OpenAI-Beta: responses_websockets=2026-02-06、originator、session-id 等
#   - 首帧: {"type": "response.create", ...Responses API 字段}
#   - 事件: response.output_text.delta / response.completed / response.failed / error
DEFAULT_BASE_URL = "https://chatgpt.com/backend-api/codex"
DEFAULT_OPENAI_BETA = "responses_websockets=2026-02-06"
DEFAULT_ORIGINATOR = "codex_chatgpt_desktop"  # ChatGPT 桌面端 Codex 的 originator
CLIENT_VERSION = "0.140.0"

_MODEL_CACHE_TTL_SECONDS = 300.0


def _setting(key: str, fallback: str) -> str:
    return str(get_setting(key, fallback)).strip()


def _setting_int(key: str, fallback: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(float(get_setting(key, str(fallback)))))
    except (TypeError, ValueError):
        return max(minimum, fallback)


class CodexWsProvider:
    """无界面 Codex 激活提供方。

    不走 HTTP、不拉起桌面端：把“你好”装包成 WebSocket 帧，直接发送到 Codex
    Responses WebSocket 端点。断线重连最多 ``ws_reconnect_limit`` 次（默认 5 次，
    与 Codex 客户端的 stream 重试次数一致）；重连只发生在“消息尚未发出”的阶段，
    一旦 turn 帧已发出，断线只上报状态未知，绝不重发，避免重复激活。
    """

    _model_cache: dict[str, tuple[float, str]] = {}

    def __init__(self) -> None:
        self.settings = get_settings()

    # ---------------------------------------------------------------- settings

    def _base_url(self) -> str:
        return _setting("ws_base_url", self.settings.ws_base_url) or DEFAULT_BASE_URL

    def _originator(self) -> str:
        return _setting("ws_originator", self.settings.ws_originator) or DEFAULT_ORIGINATOR

    def _openai_beta(self) -> str:
        return (
            _setting("ws_openai_beta", self.settings.ws_openai_beta)
            or DEFAULT_OPENAI_BETA
        )

    def _reconnect_limit(self) -> int:
        return _setting_int("ws_reconnect_limit", self.settings.ws_reconnect_limit)

    def _connect_timeout(self) -> float:
        try:
            value = float(
                _setting(
                    "ws_connect_timeout_seconds",
                    str(self.settings.ws_connect_timeout_seconds),
                )
            )
        except ValueError:
            value = float(self.settings.ws_connect_timeout_seconds)
        return max(1.0, value)

    def _turn_timeout(self) -> float:
        try:
            value = float(
                _setting(
                    "ws_turn_timeout_seconds",
                    str(self.settings.ws_turn_timeout_seconds),
                )
            )
        except ValueError:
            value = float(self.settings.ws_turn_timeout_seconds)
        return max(10.0, value)

    # ------------------------------------------------------------------ headers

    def _headers(
        self,
        access_token: str,
        account_id: str,
        *,
        model: str = "",
        session_id: str = "",
        thread_id: str = "",
    ) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": (
                f"{self._originator()}/{CLIENT_VERSION} "
                "(Windows; x86_64) xianyu-codex-fulfillment"
            ),
            "originator": self._originator(),
            "OpenAI-Beta": self._openai_beta(),
            "version": CLIENT_VERSION,
        }
        if account_id:
            headers["ChatGPT-Account-ID"] = account_id
        if thread_id:
            headers["x-client-request-id"] = thread_id
            headers["thread-id"] = thread_id
        if session_id:
            headers["session-id"] = session_id
        if model:
            headers["x-codex-routing-hint"] = f"model={model}"
        return headers

    # -------------------------------------------------------------- model pick

    async def _fetch_model_catalog(
        self,
        access_token: str,
        account_id: str,
    ) -> tuple[str, str]:
        """从账号模型目录选出默认模型；返回 (slug, error)。"""
        base_url = self._base_url().rstrip("/")
        headers = self._headers(access_token, account_id)
        url = f"{base_url}/models?client_version={CLIENT_VERSION}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
            if response.status_code != 200:
                return "", f"模型目录请求失败: HTTP {response.status_code}"
            payload = response.json()
            models = payload.get("models") if isinstance(payload, dict) else None
            if not isinstance(models, list) or not models:
                return "", "模型目录为空"
            default = next(
                (entry for entry in models if entry.get("is_default")),
                models[0],
            )
            slug = str((default or {}).get("slug") or "").strip()
            if not slug:
                return "", "模型目录缺少 slug"
            return slug, ""
        except httpx.HTTPError as exc:
            return "", f"模型目录请求异常: {exc}"

    async def _cached_model(
        self,
        item: dict[str, Any],
        access_token: str,
        account_id: str,
    ) -> tuple[str, str]:
        explicit = _setting("ws_model", self.settings.ws_model)
        if explicit:
            return explicit, ""
        key = account_id or str(item.get("email") or "") or "default"
        now = time.monotonic()
        cached = self._model_cache.get(key)
        if cached and cached[0] > now:
            return cached[1], ""
        slug, error = await self._fetch_model_catalog(access_token, account_id)
        if slug:
            self._model_cache[key] = (now + _MODEL_CACHE_TTL_SECONDS, slug)
        return slug, error

    # --------------------------------------------------------------- turn flow

    @staticmethod
    def _request_frame(prompt: str, model: str, ids: dict[str, str]) -> dict[str, Any]:
        return {
            "type": "response.create",
            "model": model,
            "instructions": "",
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                }
            ],
            "tool_choice": "auto",
            "parallel_tool_calls": True,
            "reasoning": {"effort": "medium"},
            "store": False,
            "stream": True,
            "include": [],
            "client_metadata": {
                "session_id": ids["session_id"],
                "thread_id": ids["thread_id"],
                "turn_id": ids["turn_id"],
            },
        }

    async def _run_turn(
        self,
        *,
        ws_url: str,
        headers: dict[str, str],
        frame: dict[str, Any],
        order_id: str,
        inventory_id: int,
        report: Callable[[str], None],
    ) -> dict[str, Any]:
        """连接、发送、读事件直到 response.completed / response.failed。

        连接阶段（尚未发送）失败会抛出异常由外层重连；turn 已发出后的任何
        中断都返回 ``sent_unknown=True`` 的结果，绝不重发。
        """
        connect_timeout = self._connect_timeout()
        turn_timeout = self._turn_timeout()
        deadline = time.monotonic() + turn_timeout
        recv_idle = min(max(30.0, turn_timeout), 300.0)

        async with websockets.connect(
            ws_url,
            additional_headers=headers,
            compression="deflate",
            open_timeout=connect_timeout,
            close_timeout=5,
            ping_interval=20,
            ping_timeout=20,
            max_size=4 * 1024 * 1024,
        ) as ws:
            report("sending")
            try:
                await asyncio.wait_for(
                    ws.send(json.dumps(frame, ensure_ascii=False)),
                    timeout=min(connect_timeout, max(1.0, deadline - time.monotonic())),
                )
            except (asyncio.TimeoutError, ConnectionClosed) as exc:
                write_audit(
                    "activation.ws_turn_send_interrupted",
                    order_id=order_id,
                    inventory_id=inventory_id,
                    payload={"error": str(exc)[:500]},
                )
                return result_dict(
                    ok=False,
                    error="WebSocket 发送阶段中断，发送结果未知",
                    stage="turn_status_unknown",
                    sent_unknown=True,
                )
            report("waiting_response")

            reply_parts: list[str] = []
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    write_audit(
                        "activation.ws_turn_timeout",
                        order_id=order_id,
                        inventory_id=inventory_id,
                        payload={"reason": "turn_timeout"},
                    )
                    return result_dict(
                        ok=False,
                        error="WebSocket 等待回复超时，发送结果未知",
                        stage="turn_status_unknown",
                        sent_unknown=True,
                    )
                try:
                    message = await asyncio.wait_for(
                        ws.recv(),
                        timeout=min(recv_idle, remaining),
                    )
                except asyncio.TimeoutError:
                    write_audit(
                        "activation.ws_turn_idle_timeout",
                        order_id=order_id,
                        inventory_id=inventory_id,
                        payload={"reason": "idle_timeout"},
                    )
                    return result_dict(
                        ok=False,
                        error="WebSocket 等待回复超时，发送结果未知",
                        stage="turn_status_unknown",
                        sent_unknown=True,
                    )
                except ConnectionClosed as exc:
                    write_audit(
                        "activation.ws_turn_connection_lost",
                        order_id=order_id,
                        inventory_id=inventory_id,
                        payload={"error": str(exc)[:500]},
                    )
                    return result_dict(
                        ok=False,
                        error="WebSocket 在收到回复前断开，发送结果未知",
                        stage="turn_status_unknown",
                        sent_unknown=True,
                    )
                if isinstance(message, (bytes, bytearray)):
                    continue
                try:
                    event = json.loads(message)
                except (TypeError, json.JSONDecodeError):
                    continue
                if not isinstance(event, dict):
                    continue
                kind = str(event.get("type") or "")
                if kind == "response.output_text.delta":
                    reply_parts.append(str(event.get("delta") or ""))
                elif kind == "response.completed":
                    reply = "".join(reply_parts).strip()
                    if not reply:
                        return result_dict(
                            ok=False,
                            error="Codex 完成回复但未包含文本",
                            stage="ws_no_reply",
                            sent_unknown=False,
                        )
                    return result_dict(
                        ok=True,
                        reply=reply[:2000],
                        stage="completed",
                        sent_unknown=False,
                    )
                elif kind in {"response.failed", "error"}:
                    error_info = event.get("error") or (
                        (event.get("response") or {}).get("error")
                    )
                    if isinstance(error_info, dict):
                        code = str(error_info.get("code") or "")
                        message = str(error_info.get("message") or "")
                    else:
                        code = ""
                        message = str(event.get("error") or event)
                    status = event.get("status")
                    if status is not None:
                        code = code or f"status_{status}"
                    raise _TurnRejected(code, message)

    async def activate(
        self,
        item: dict[str, Any],
        prompt: str = "你好",
        stage_callback: Callable[[str], None] | None = None,
        instance: Any | None = None,
    ) -> dict[str, Any]:
        settings = get_settings()
        order_id = str(item.get("reserved_order_id") or "")
        inventory_id = int(item.get("id") or 0)
        if settings.dry_run:
            return result_dict(
                ok=True,
                reply="dry-run: 已模拟通过 Codex WebSocket 发送你好",
                stage="dry_run",
                provider="ws",
            )

        def report(stage: str) -> None:
            if stage_callback:
                stage_callback(stage)

        report("switching_account")
        tokens = _extract_oauth_tokens(item)
        if not tokens.access_token:
            return result_dict(
                ok=False,
                error="库存缺少 WebSocket 激活所需的 access_token",
                stage="ws_missing_credentials",
                sent_unknown=False,
                provider="ws",
            )
        if not tokens.account_id:
            return result_dict(
                ok=False,
                error="库存缺少 WebSocket 激活所需的账号 ID",
                stage="ws_missing_credentials",
                sent_unknown=False,
                provider="ws",
            )

        model, model_error = await self._cached_model(
            item, tokens.access_token, tokens.account_id
        )
        if not model:
            write_audit(
                "activation.ws_models_failed",
                order_id=order_id,
                inventory_id=inventory_id,
                payload={"error": model_error},
            )
            return result_dict(
                ok=False,
                error=model_error,
                stage="ws_models_failed",
                sent_unknown=False,
                provider="ws",
            )

        base_url = self._base_url().rstrip("/")
        ws_url = f"{base_url}/responses"
        if ws_url.startswith("https://"):
            ws_url = "wss://" + ws_url[len("https://") :]
        elif ws_url.startswith("http://"):
            ws_url = "ws://" + ws_url[len("http://") :]

        ids = {
            "session_id": uuid.uuid4().hex,
            "thread_id": uuid.uuid4().hex,
            "turn_id": uuid.uuid4().hex,
        }
        headers = self._headers(
            tokens.access_token,
            tokens.account_id,
            model=model,
            session_id=ids["session_id"],
            thread_id=ids["thread_id"],
        )
        frame = self._request_frame(prompt, model, ids)

        limit = self._reconnect_limit()
        last_error = ""
        for attempt in range(1, limit + 1):
            if attempt > 1:
                delay = min(8.0, 0.5 * (2 ** (attempt - 2))) + random.uniform(0, 0.3)
                await asyncio.sleep(delay)
            try:
                result = await self._run_turn(
                    ws_url=ws_url,
                    headers=headers,
                    frame=frame,
                    order_id=order_id,
                    inventory_id=inventory_id,
                    report=report,
                )
                result["provider"] = "ws"
                result["thread_id"] = ids["thread_id"]
                result["turn_id"] = ids["turn_id"]
                result["model"] = model
                result["attempts"] = attempt
                if result.get("ok"):
                    write_audit(
                        "activation.ws_turn_completed",
                        order_id=order_id,
                        inventory_id=inventory_id,
                        payload={"model": model, "attempts": attempt},
                    )
                elif result.get("sent_unknown"):
                    write_audit(
                        "activation.ws_turn_status_unknown",
                        order_id=order_id,
                        inventory_id=inventory_id,
                        payload={"model": model, "attempts": attempt},
                    )
                return result
            except _TurnRejected as exc:
                write_audit(
                    "activation.ws_turn_rejected",
                    order_id=order_id,
                    inventory_id=inventory_id,
                    payload={
                        "code": exc.code,
                        "message": exc.message[:500],
                        "attempts": attempt,
                    },
                )
                return result_dict(
                    ok=False,
                    error=f"Codex 拒绝本次请求: {exc.code} {exc.message}".strip()[:2000],
                    stage="ws_turn_failed",
                    sent_unknown=False,
                    provider="ws",
                    thread_id=ids["thread_id"],
                    turn_id=ids["turn_id"],
                    model=model,
                    attempts=attempt,
                )
            except InvalidStatus as exc:
                status = getattr(exc.response, "status_code", 0)
                last_error = f"握手被拒绝: HTTP {status}"
                if status in {400, 401, 403}:
                    write_audit(
                        "activation.ws_handshake_rejected",
                        order_id=order_id,
                        inventory_id=inventory_id,
                        payload={"status": status},
                    )
                    return result_dict(
                        ok=False,
                        error=f"WebSocket 握手被拒绝: HTTP {status}（凭证或账号状态异常）",
                        stage="ws_auth_failed" if status in {401, 403} else "ws_http_error",
                        sent_unknown=False,
                        provider="ws",
                        thread_id=ids["thread_id"],
                        turn_id=ids["turn_id"],
                        model=model,
                        attempts=attempt,
                    )
                write_audit(
                    "activation.ws_reconnect",
                    order_id=order_id,
                    inventory_id=inventory_id,
                    payload={"attempt": attempt, "limit": limit, "error": last_error[:500]},
                )
            except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as exc:
                last_error = str(exc) or exc.__class__.__name__
                write_audit(
                    "activation.ws_reconnect",
                    order_id=order_id,
                    inventory_id=inventory_id,
                    payload={"attempt": attempt, "limit": limit, "error": last_error[:500]},
                )

        report("switching_account")
        write_audit(
            "activation.ws_connect_failed",
            order_id=order_id,
            inventory_id=inventory_id,
            payload={"attempts": limit, "error": last_error[:500]},
        )
        return result_dict(
            ok=False,
            error=f"WebSocket 连接失败（已重试 {limit} 次）: {last_error}"[:2000],
            stage="ws_connect_failed",
            sent_unknown=False,
            provider="ws",
            thread_id=ids["thread_id"],
            turn_id=ids["turn_id"],
            model=model,
            attempts=limit,
        )


class _TurnRejected(Exception):
    """turn 被服务端明确拒绝（未发送成功），携带错误码与信息。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code} {message}".strip())
        self.code = code
        self.message = message
