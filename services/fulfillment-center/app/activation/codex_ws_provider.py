from __future__ import annotations

import asyncio
import json
import random
import secrets
import time
import uuid
from typing import Any, Callable

import httpx
import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatus

from ..audit import write_audit
from ..config import get_settings
from ..inventory import activation_eligibility
from ..settings_store import get_setting, update_settings
from .base_provider import result_dict
from .codex_desktop_wire import (
    DEFAULT_TOOLS_JSON,
    DESKTOP_APP_CONTEXT,
    DESKTOP_APPS_INSTRUCTIONS,
    DESKTOP_BASE_INSTRUCTIONS,
    DESKTOP_PERMISSIONS_INSTRUCTIONS,
    DESKTOP_RECOMMENDED_PLUGINS,
    DESKTOP_SKILLS_INSTRUCTIONS,
    desktop_environment_context,
)
from .desktop_provider import _extract_oauth_tokens

# 与真实 Codex Desktop（0.147.0-alpha.6.6）对齐的传输参数，参考 openai/codex 源码：
#   - 端点: wss://chatgpt.com/backend-api/codex/responses
#   - originator: "Codex Desktop"；握手带 OpenAI-Beta、version、session/thread/window id
#   - 先发 generate:false 预热帧拿到 warm response id 与 x-codex-turn-state，
#     再在同一连接上用 previous_response_id 发送正式 turn
DEFAULT_BASE_URL = "https://chatgpt.com/backend-api/codex"
DEFAULT_OPENAI_BETA = "responses_websockets=2026-02-06"
DEFAULT_ORIGINATOR = "Codex Desktop"
DEFAULT_CLIENT_VERSION = "0.147.0-alpha.6.6"

_MODEL_CACHE_TTL_SECONDS = 300.0
X_CODEX_TURN_STATE = "x-codex-turn-state"
X_CODEX_TURN_METADATA = "x-codex-turn-metadata"
X_CODEX_INSTALLATION_ID = "x-codex-installation-id"
X_CODEX_WINDOW_ID = "x-codex-window-id"
WS_TRACEPARENT_KEY = "ws_request_header_traceparent"


def _setting(key: str, fallback: str) -> str:
    return str(get_setting(key, fallback)).strip()


def _setting_int(key: str, fallback: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(float(get_setting(key, str(fallback)))))
    except (TypeError, ValueError):
        return max(minimum, fallback)


def _uuid7() -> str:
    """UUIDv7（RFC 9562）：与桌面端 session/thread/turn/window id 同格式。"""
    ts_ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF  # 48-bit
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (
        (ts_ms << 80)
        | (0x7 << 76)          # version 7
        | (rand_a << 64)
        | (0b10 << 62)         # variant 10
        | rand_b
    )
    text = f"{value:032x}"
    return f"{text[0:8]}-{text[8:12]}-{text[12:16]}-{text[16:20]}-{text[20:32]}"


def _traceparent() -> str:
    trace = secrets.token_hex(16)
    span = secrets.token_hex(8)
    return f"00-{trace}-{span}-01"


class CodexWsProvider:
    """无界面 Codex 激活：按真实 Codex Desktop 的 WebSocket 会话链路发送“你好”。

    与桌面端一致的行为：
    - originator "Codex Desktop"、桌面版 User-Agent/version 头、UUIDv7 会话 id
    - 同一连接上先发 generate:false 预热帧，再带 previous_response_id 发正式 turn
    - 完整 instructions、桌面 app-context/skills/permissions 上下文、工具声明、
      prompt_cache_key、service_tier、include、x-codex-turn-metadata
    - 只在“正式 turn 尚未发出”的阶段重连（默认 5 次），发出后断线绝不重发
    """

    _model_cache: dict[str, tuple[float, str, str, str]] = {}

    def __init__(self) -> None:
        self.settings = get_settings()

    # ---------------------------------------------------------------- settings

    def _base_url(self) -> str:
        return _setting("ws_base_url", self.settings.ws_base_url) or DEFAULT_BASE_URL

    def _proxy_url(self) -> str:
        return _setting("ws_proxy_url", self.settings.ws_proxy_url)

    def _originator(self) -> str:
        return _setting("ws_originator", self.settings.ws_originator) or DEFAULT_ORIGINATOR

    def _client_version(self) -> str:
        return (
            _setting("ws_client_version", self.settings.ws_client_version)
            or DEFAULT_CLIENT_VERSION
        )

    def _openai_beta(self) -> str:
        return _setting("ws_openai_beta", self.settings.ws_openai_beta) or DEFAULT_OPENAI_BETA

    def _service_tier(self) -> str:
        return _setting("ws_service_tier", self.settings.ws_service_tier) or "priority"

    def _reasoning_effort(self) -> str:
        return _setting("ws_reasoning_effort", self.settings.ws_reasoning_effort) or "medium"

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

    def _tools(self) -> list[Any]:
        raw = _setting("ws_tools_json", self.settings.ws_tools_json)
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return list(DEFAULT_TOOLS_JSON)

    def _installation_id(self) -> str:
        current = _setting("ws_installation_id", self.settings.ws_installation_id)
        if current and len(current) >= 32:
            return current
        generated = str(uuid.uuid4())
        update_settings({"ws_installation_id": generated})
        return generated

    # ------------------------------------------------------------------ headers

    def _headers(
        self,
        access_token: str,
        account_id: str,
        *,
        model: str = "",
        tier: str = "",
        session_id: str = "",
        thread_id: str = "",
        window_id: str = "",
    ) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": (
                f"{self._originator()}/{self._client_version()} "
                f"(Windows 10.0.26100; x86_64) unknown"
            ),
            "originator": self._originator(),
            "OpenAI-Beta": self._openai_beta(),
            "version": self._client_version(),
        }
        if account_id:
            headers["ChatGPT-Account-ID"] = account_id
        if thread_id:
            headers["x-client-request-id"] = thread_id
            headers["thread-id"] = thread_id
        if session_id:
            headers["session-id"] = session_id
        if window_id:
            headers["x-codex-window-id"] = window_id
        if model:
            hint = f"model={model}"
            if tier:
                hint += f";tier={tier}"
            headers["x-codex-routing-hint"] = hint
        return headers

    # -------------------------------------------------------------- model pick

    async def _fetch_model_catalog(
        self,
        access_token: str,
        account_id: str,
    ) -> tuple[str, str, str, str]:
        """返回 (slug, default_service_tier, default_reasoning_level, error)。"""
        base_url = self._base_url().rstrip("/")
        headers = self._headers(access_token, account_id)
        url = f"{base_url}/models?client_version={self._client_version()}"
        proxy = self._proxy_url() or None
        try:
            async with httpx.AsyncClient(timeout=10.0, proxy=proxy) as client:
                response = await client.get(url, headers=headers)
            if response.status_code != 200:
                return "", "", "", f"模型目录请求失败: HTTP {response.status_code}"
            payload = response.json()
            models = payload.get("models") if isinstance(payload, dict) else None
            if not isinstance(models, list) or not models:
                return "", "", "", "模型目录为空"
            default = next(
                (entry for entry in models if entry.get("is_default")),
                models[0],
            )
            slug = str((default or {}).get("slug") or "").strip()
            if not slug:
                return "", "", "", "模型目录缺少 slug"
            tier = str((default or {}).get("default_service_tier") or "").strip()
            effort = str((default or {}).get("default_reasoning_level") or "").strip()
            return slug, tier, effort, ""
        except httpx.HTTPError as exc:
            return "", "", "", f"模型目录请求异常: {exc}"

    async def _cached_model(
        self,
        item: dict[str, Any],
        access_token: str,
        account_id: str,
    ) -> tuple[str, str, str, str]:
        explicit = _setting("ws_model", self.settings.ws_model)
        if explicit:
            return explicit, "", "", ""
        key = account_id or str(item.get("email") or "") or "default"
        now = time.monotonic()
        cached = self._model_cache.get(key)
        if cached and cached[0] > now:
            return cached[1], cached[2], cached[3], ""
        slug, tier, effort, error = await self._fetch_model_catalog(access_token, account_id)
        if slug:
            self._model_cache[key] = (now + _MODEL_CACHE_TTL_SECONDS, slug, tier, effort)
        return slug, tier, effort, error

    # ---------------------------------------------------------------- turn flow

    @staticmethod
    def _turn_metadata(
        ids: dict[str, str], request_kind: str, *, turn_started_ms: int = 0
    ) -> str:
        payload: dict[str, Any] = {
            "installation_id": ids["installation_id"],
            "session_id": ids["session_id"],
            "thread_id": ids["thread_id"],
            "window_id": ids["window_id"],
            "request_kind": request_kind,
        }
        if turn_started_ms:
            payload["turn_started_at_unix_ms"] = turn_started_ms
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def _client_metadata(
        self,
        ids: dict[str, str],
        request_kind: str,
        *,
        turn_started_ms: int = 0,
        turn_state: str = "",
    ) -> dict[str, str]:
        metadata = {
            X_CODEX_INSTALLATION_ID: ids["installation_id"],
            "session_id": ids["session_id"],
            "thread_id": ids["thread_id"],
            X_CODEX_WINDOW_ID: ids["window_id"],
            X_CODEX_TURN_METADATA: self._turn_metadata(
                ids, request_kind, turn_started_ms=turn_started_ms
            ),
            WS_TRACEPARENT_KEY: _traceparent(),
        }
        if request_kind == "turn":
            metadata["turn_id"] = ids["turn_id"]
        if turn_state:
            metadata[X_CODEX_TURN_STATE] = turn_state
        return metadata

    def _warmup_frame(
        self,
        *,
        model: str,
        tier: str,
        effort: str,
        ids: dict[str, str],
        cwd: str,
    ) -> dict[str, Any]:
        tools = self._tools()
        developer_content = [
            {"type": "input_text", "text": DESKTOP_APP_CONTEXT},
            {"type": "input_text", "text": DESKTOP_SKILLS_INSTRUCTIONS},
            {"type": "input_text", "text": DESKTOP_PERMISSIONS_INSTRUCTIONS},
            {"type": "input_text", "text": DESKTOP_APPS_INSTRUCTIONS},
        ]
        plugins_content = [
            {"type": "input_text", "text": DESKTOP_RECOMMENDED_PLUGINS},
            {"type": "input_text", "text": desktop_environment_context(cwd)},
        ]
        frame: dict[str, Any] = {
            "type": "response.create",
            "model": model,
            "instructions": DESKTOP_BASE_INSTRUCTIONS,
            "input": [
                {
                    "type": "message",
                    "id": f"msg_{ids['dev_msg_id']}",
                    "role": "developer",
                    "content": developer_content,
                },
                {
                    "type": "message",
                    "id": f"msg_{ids['env_msg_id']}",
                    "role": "user",
                    "content": plugins_content,
                },
            ],
            "tools": tools,
            "tool_choice": "auto",
            "parallel_tool_calls": True,
            "reasoning": {"effort": effort},
            "store": False,
            "stream": True,
            "include": ["reasoning.encrypted_content"],
            "prompt_cache_key": ids["session_id"],
            "generate": False,
            "client_metadata": self._client_metadata(ids, "prewarm"),
        }
        if tier:
            frame["service_tier"] = tier
        return frame

    def _turn_frame(
        self,
        *,
        prompt: str,
        model: str,
        tier: str,
        effort: str,
        ids: dict[str, str],
        previous_response_id: str,
        turn_state: str,
        turn_started_ms: int,
        cwd: str,
    ) -> dict[str, Any]:
        tools = self._tools()
        frame: dict[str, Any] = {
            "type": "response.create",
            "model": model,
            "instructions": DESKTOP_BASE_INSTRUCTIONS,
            "previous_response_id": previous_response_id,
            "input": [
                {
                    "type": "message",
                    "id": f"msg_{ids['user_msg_id']}",
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                }
            ],
            "tools": tools,
            "tool_choice": "auto",
            "parallel_tool_calls": True,
            "reasoning": {"effort": effort},
            "store": False,
            "stream": True,
            "include": ["reasoning.encrypted_content"],
            "prompt_cache_key": ids["session_id"],
            "client_metadata": self._client_metadata(
                ids,
                "turn",
                turn_started_ms=turn_started_ms,
                turn_state=turn_state,
            ),
        }
        if tier:
            frame["service_tier"] = tier
        return frame

    async def _read_until_completed(
        self,
        ws: Any,
        *,
        order_id: str,
        inventory_id: int,
        deadline: float,
        turn_state_holder: dict[str, str],
        sent_turn: bool,
    ) -> dict[str, Any]:
        """读取事件直到 response.completed / response.failed。

        ``sent_turn`` 为 True 时任何中断都返回 sent_unknown=True；
        为 False（预热阶段）时中断会抛出异常由外层安全重连。
        """
        recv_idle = min(max(30.0, self._turn_timeout()), 300.0)
        reply_parts: list[str] = []
        completed = False
        response_id = ""
        while not completed:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                error = "WebSocket 等待回复超时"
                if sent_turn:
                    write_audit(
                        "activation.ws_turn_timeout",
                        order_id=order_id,
                        inventory_id=inventory_id,
                        payload={"reason": "turn_timeout"},
                    )
                    return result_dict(
                        ok=False,
                        error=f"{error}，发送结果未知",
                        stage="turn_status_unknown",
                        sent_unknown=True,
                    )
                raise asyncio.TimeoutError(error)
            try:
                message = await asyncio.wait_for(
                    ws.recv(),
                    timeout=min(recv_idle, remaining),
                )
            except asyncio.TimeoutError:
                if sent_turn:
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
                raise
            except ConnectionClosed as exc:
                if sent_turn:
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
                raise
            if isinstance(message, (bytes, bytearray)):
                continue
            try:
                event = json.loads(message)
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(event, dict):
                continue
            kind = str(event.get("type") or "")
            if kind == "response.created":
                response = event.get("response") or {}
                if isinstance(response, dict) and response.get("id"):
                    response_id = str(response["id"])
            elif kind == "response.metadata":
                headers = event.get("headers") or {}
                if isinstance(headers, dict):
                    state = str(headers.get(X_CODEX_TURN_STATE) or "")
                    if state:
                        turn_state_holder["state"] = state
            elif kind == "response.output_text.delta":
                reply_parts.append(str(event.get("delta") or ""))
            elif kind == "response.completed":
                completed = True
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
        return {
            "completed": True,
            "response_id": response_id,
            "reply": "".join(reply_parts).strip(),
        }

    async def _run_session(
        self,
        *,
        ws_url: str,
        headers: dict[str, str],
        ids: dict[str, str],
        model: str,
        tier: str,
        effort: str,
        prompt: str,
        order_id: str,
        inventory_id: int,
        cwd: str,
        report: Callable[[str], None],
    ) -> dict[str, Any]:
        """单次连接：预热帧 → 正式 turn 帧（同一连接复用）。"""
        connect_timeout = self._connect_timeout()
        turn_timeout = self._turn_timeout()
        turn_state_holder: dict[str, str] = {}
        proxy = self._proxy_url() or None

        async with websockets.connect(
            ws_url,
            additional_headers=headers,
            compression="deflate",
            open_timeout=connect_timeout,
            close_timeout=5,
            ping_interval=20,
            ping_timeout=20,
            max_size=8 * 1024 * 1024,
            proxy=proxy,
        ) as ws:
            # 握手响应头里也可能带 x-codex-turn-state
            response = getattr(ws, "response", None)
            if response is not None:
                state = str(response.headers.get(X_CODEX_TURN_STATE) or "")
                if state:
                    turn_state_holder["state"] = state

            # 1) 预热帧（generate:false）：服务端接受后返回 warm response id
            warmup = self._warmup_frame(
                model=model, tier=tier, effort=effort, ids=ids, cwd=cwd
            )
            report("switching_account")
            try:
                await asyncio.wait_for(
                    ws.send(json.dumps(warmup, ensure_ascii=False)),
                    timeout=connect_timeout,
                )
            except (asyncio.TimeoutError, ConnectionClosed):
                # 预热帧未送达：整条会话还没产生任何用户可见内容，可安全重连
                raise asyncio.TimeoutError("预热帧发送失败")

            deadline = time.monotonic() + min(60.0, turn_timeout)
            warm_result = await self._read_until_completed(
                ws,
                order_id=order_id,
                inventory_id=inventory_id,
                deadline=deadline,
                turn_state_holder=turn_state_holder,
                sent_turn=False,
            )
            if not warm_result.get("completed"):
                raise asyncio.TimeoutError("预热阶段未完成")
            previous_response_id = warm_result.get("response_id") or ""

            # 2) 正式 turn 帧：previous_response_id 引用预热结果，同一连接复用
            turn_started_ms = int(time.time() * 1000)
            turn = self._turn_frame(
                prompt=prompt,
                model=model,
                tier=tier,
                effort=effort,
                ids=ids,
                previous_response_id=previous_response_id,
                turn_state=turn_state_holder.get("state", ""),
                turn_started_ms=turn_started_ms,
                cwd=cwd,
            )
            report("sending")
            try:
                await asyncio.wait_for(
                    ws.send(json.dumps(turn, ensure_ascii=False)),
                    timeout=connect_timeout,
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

            deadline = time.monotonic() + turn_timeout
            turn_result = await self._read_until_completed(
                ws,
                order_id=order_id,
                inventory_id=inventory_id,
                deadline=deadline,
                turn_state_holder=turn_state_holder,
                sent_turn=True,
            )
            if not turn_result.get("completed"):
                return turn_result
            reply = turn_result.get("reply") or ""
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
        eligible, eligibility_reason = activation_eligibility(item)
        if not eligible:
            return result_dict(
                ok=False,
                error=f"库存不可正式激活: {eligibility_reason}",
                stage="ws_ineligible",
                sent_unknown=False,
                provider="ws",
            )
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

        model, catalog_tier, catalog_effort, model_error = await self._cached_model(
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
        tier = self._service_tier() or catalog_tier
        effort = self._reasoning_effort() or catalog_effort or "medium"

        base_url = self._base_url().rstrip("/")
        ws_url = f"{base_url}/responses"
        if ws_url.startswith("https://"):
            ws_url = "wss://" + ws_url[len("https://") :]
        elif ws_url.startswith("http://"):
            ws_url = "ws://" + ws_url[len("http://") :]

        cwd = str(settings.database_path.parent)
        ids = {
            "installation_id": self._installation_id(),
            "session_id": _uuid7(),
            "thread_id": _uuid7(),
            "window_id": _uuid7(),
            "turn_id": _uuid7(),
            "dev_msg_id": _uuid7(),
            "env_msg_id": _uuid7(),
            "user_msg_id": _uuid7(),
        }
        headers = self._headers(
            tokens.access_token,
            tokens.account_id,
            model=model,
            tier=tier,
            session_id=ids["session_id"],
            thread_id=ids["thread_id"],
            window_id=ids["window_id"],
        )

        limit = self._reconnect_limit()
        last_error = ""
        for attempt in range(1, limit + 1):
            if attempt > 1:
                delay = min(8.0, 0.5 * (2 ** (attempt - 2))) + random.uniform(0, 0.3)
                await asyncio.sleep(delay)
            try:
                result = await self._run_session(
                    ws_url=ws_url,
                    headers=headers,
                    ids=ids,
                    model=model,
                    tier=tier,
                    effort=effort,
                    prompt=prompt,
                    order_id=order_id,
                    inventory_id=inventory_id,
                    cwd=cwd,
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
