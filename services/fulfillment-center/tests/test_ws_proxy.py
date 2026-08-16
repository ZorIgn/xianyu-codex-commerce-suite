from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import patch


class _FakeWebSocket:
    """两帧会话：预热帧 → created/completed，turn 帧 → delta/completed。"""

    def __init__(self) -> None:
        self.sent_frames: list[dict] = []
        self._events = iter(
            [
                json.dumps({"type": "response.created", "response": {"id": "warm-resp-1"}}),
                json.dumps({"type": "response.completed", "response": {"id": "warm-resp-1"}}),
                json.dumps({"type": "response.output_text.delta", "delta": "ok"}),
                json.dumps({"type": "response.completed", "response": {"id": "resp-1"}}),
            ]
        )

    async def send(self, message: str) -> None:
        self.sent_frames.append(json.loads(message))

    async def recv(self) -> str:
        return next(self._events)


class _FakeConnection:
    def __init__(self, websocket: _FakeWebSocket) -> None:
        self.websocket = websocket

    async def __aenter__(self) -> _FakeWebSocket:
        return self.websocket

    async def __aexit__(self, *args: object) -> None:
        return None


class WebSocketProxyTest(unittest.TestCase):
    def test_proxy_passed_and_desktop_two_frame_session(self) -> None:
        from app.activation.codex_ws_provider import CodexWsProvider

        captured: dict[str, object] = {}
        websocket = _FakeWebSocket()

        def fake_connect(uri: str, **kwargs: object) -> _FakeConnection:
            captured["uri"] = uri
            captured.update(kwargs)
            return _FakeConnection(websocket)

        def fake_setting(key: str, fallback: str) -> str:
            if key == "ws_proxy_url":
                return "http://127.0.0.1:7890"
            if key == "ws_tools_json":
                return "[]"
            return fallback

        provider = CodexWsProvider()
        with (
            patch("app.activation.codex_ws_provider.get_setting", side_effect=fake_setting),
            patch("app.activation.codex_ws_provider.websockets.connect", side_effect=fake_connect),
        ):
            result = asyncio.run(
                provider._run_session(
                    ws_url="wss://chatgpt.com/backend-api/codex/responses",
                    headers={"Authorization": "Bearer redacted"},
                    ids={
                        "installation_id": "installation-1",
                        "session_id": "session-1",
                        "thread_id": "thread-1",
                        "window_id": "window-1",
                        "turn_id": "turn-1",
                        "dev_msg_id": "dev-1",
                        "env_msg_id": "env-1",
                        "user_msg_id": "user-1",
                    },
                    model="gpt-5.6-luna",
                    tier="priority",
                    effort="medium",
                    prompt="你好",
                    order_id="proxy-test",
                    inventory_id=1,
                    cwd="E:/account",
                    report=lambda _stage: None,
                )
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["reply"], "ok")
        self.assertEqual(captured["proxy"], "http://127.0.0.1:7890")

        warmup, turn = websocket.sent_frames[0], websocket.sent_frames[1]
        self.assertEqual(warmup["type"], "response.create")
        self.assertIs(warmup["generate"], False)
        self.assertIn("instructions", warmup)
        self.assertEqual(turn["type"], "response.create")
        self.assertEqual(turn["previous_response_id"], "warm-resp-1")
        self.assertEqual(turn["input"][0]["role"], "user")
        self.assertEqual(turn["input"][0]["content"][0]["text"], "你好")
        self.assertEqual(turn["client_metadata"]["turn_id"], "turn-1")


if __name__ == "__main__":
    unittest.main()
