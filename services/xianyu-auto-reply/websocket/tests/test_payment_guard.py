from __future__ import annotations

import asyncio
import os
import sys
import unittest
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


SERVICE_ROOT = Path(__file__).resolve().parents[2]
WEBSOCKET_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEBSOCKET_ROOT))
sys.path.insert(0, str(SERVICE_ROOT))

from app.services.xianyu.auto_delivery_handler import AutoDeliveryHandler  # noqa: E402
from common.services.order_payment_guard import (  # noqa: E402
    DEFAULT_BASE_DELAY_SECONDS,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_MAX_DELAY_SECONDS,
    MAX_ALLOWED_ATTEMPTS,
    MAX_ALLOWED_DELAY_SECONDS,
    PAYMENT_GUARD_METADATA_KEY,
    build_ready_state,
    build_retry_state,
    classify_payment_state,
    classify_terminal_reason,
    normalize_retry_config,
)
from common.services.order_service import OrderService, OrderStatusChecker  # noqa: E402


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return self

    def first(self):
        return self.value


class _Session:
    def __init__(self, order):
        self.order = order
        self.statements = []
        self.commit_count = 0
        self.rollback_count = 0

    async def execute(self, statement):
        self.statements.append(statement)
        if len(self.statements) == 1:
            return _ScalarResult(self.order)
        return _ScalarResult(None)

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_count += 1


class PaymentGuardTests(unittest.IsolatedAsyncioTestCase):
    def test_zero_race_is_retryable_then_positive_amount_proceeds(self):
        pending = classify_payment_state(
            amount="0",
            can_ship=True,
            status_reason="订单状态暂不可用",
            platform_status="待发货",
            local_status="pending_ship",
        )
        self.assertEqual(pending.action, "retry")
        self.assertEqual(pending.reason["code"], "amount_not_synced")
        self.assertFalse(pending.reason["amount_authoritative"])

        retry_state = build_retry_state(
            None,
            pending.reason,
            max_attempts=DEFAULT_MAX_ATTEMPTS,
            base_delay_seconds=DEFAULT_BASE_DELAY_SECONDS,
            max_delay_seconds=DEFAULT_MAX_DELAY_SECONDS,
            now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(retry_state["state"], "retrying")
        self.assertEqual(retry_state["attempt"], 1)
        self.assertEqual(retry_state["max"], DEFAULT_MAX_ATTEMPTS)
        self.assertIsNotNone(retry_state["next_retry"])

        ready = classify_payment_state(
            amount="12.50",
            can_ship=True,
            status_reason="订单已付款，可以发货",
            platform_status="待发货",
            local_status="pending_ship",
            amount_authoritative=True,
        )
        self.assertEqual(ready.action, "proceed")
        self.assertEqual(ready.reason["code"], "amount_synced")

        ready_state = build_ready_state(
            retry_state,
            amount="12.50",
            platform_status="待发货",
            now=datetime(2026, 1, 1, 0, 0, 2, tzinfo=timezone.utc),
        )
        self.assertEqual(ready_state["state"], "ready")
        self.assertIsNone(ready_state["next_retry"])

    def test_terminal_states_stop_and_generic_refresh_failure_retries(self):
        terminal_cases = (
            ("退款中", "order_refunded"),
            ("交易关闭", "order_closed"),
            ("订单已取消", "order_cancelled"),
            ("支付失败", "transaction_failed"),
            ("failed", "transaction_failed"),
        )
        for status, expected_code in terminal_cases:
            with self.subTest(status=status):
                reason = classify_terminal_reason(
                    status_reason=status if status != "failed" else None,
                    platform_status="failed" if status == "failed" else "未知",
                    local_status="pending_ship",
                )
                self.assertIsNotNone(reason)
                self.assertEqual(reason["code"], expected_code)

        refresh_failure = classify_terminal_reason(
            status_reason="获取订单详情失败: network timeout",
            platform_status="未知",
            local_status="pending_ship",
        )
        self.assertIsNone(refresh_failure)
        retry = classify_payment_state(
            amount=None,
            can_ship=None,
            status_reason="刷新失败，请稍后重试",
            platform_status="未知",
            local_status="pending_ship",
        )
        self.assertEqual(retry.action, "retry")
        self.assertEqual(retry.reason["code"], "amount_not_synced")

        checker = object.__new__(OrderStatusChecker)
        can_ship, reason, _ = checker._analyze_can_ship(
            [
                {"title": "已付款", "completed": True},
                {"title": "待发货", "completed": False},
                {"title": "获取订单详情失败", "completed": False},
            ]
        )
        self.assertTrue(can_ship)
        self.assertNotIn("失败", reason)

    def test_authoritative_zero_and_unknown_amount_have_distinct_exhaustion_reasons(self):
        authoritative_zero = classify_payment_state(
            amount="0.00",
            can_ship=True,
            status_reason="订单已付款，可以发货",
            platform_status="待发货",
            local_status="pending_ship",
            amount_authoritative=True,
        )
        state = build_retry_state(None, authoritative_zero.reason, max_attempts=2)
        state = build_retry_state(state, authoritative_zero.reason, max_attempts=2)
        self.assertEqual(state["state"], "stopped")
        self.assertEqual(state["reason"]["code"], "zero_amount_confirmed")
        self.assertIsNone(state["next_retry"])

        unknown = classify_payment_state(
            amount="0",
            can_ship=None,
            status_reason="获取订单详情失败",
            platform_status="未知",
            local_status="pending_ship",
        )
        unknown_state = build_retry_state(None, unknown.reason, max_attempts=1)
        self.assertEqual(unknown_state["state"], "stopped")
        self.assertEqual(unknown_state["reason"]["code"], "amount_sync_retry_exhausted")

    def test_invalid_and_huge_retry_settings_are_finite(self):
        self.assertEqual(
            normalize_retry_config("not-an-int", "not-a-number", "nan"),
            (DEFAULT_MAX_ATTEMPTS, DEFAULT_BASE_DELAY_SECONDS, DEFAULT_MAX_DELAY_SECONDS),
        )
        self.assertEqual(
            normalize_retry_config("999999999", "999999999", "999999999"),
            (MAX_ALLOWED_ATTEMPTS, MAX_ALLOWED_DELAY_SECONDS, MAX_ALLOWED_DELAY_SECONDS),
        )

        handler = object.__new__(AutoDeliveryHandler)
        with patch.dict(
            os.environ,
            {
                "AUTO_DELIVERY_PAYMENT_MAX_ATTEMPTS": "999999999",
                "AUTO_DELIVERY_PAYMENT_RETRY_BASE_SECONDS": "999999999",
                "AUTO_DELIVERY_PAYMENT_RETRY_MAX_SECONDS": "999999999",
            },
            clear=False,
        ):
            self.assertEqual(
                handler._payment_guard_config(),
                (MAX_ALLOWED_ATTEMPTS, MAX_ALLOWED_DELAY_SECONDS, MAX_ALLOWED_DELAY_SECONDS),
            )

        state = None
        reason = {"code": "amount_not_synced", "amount": None}
        for _ in range(MAX_ALLOWED_ATTEMPTS):
            state = build_retry_state(
                state,
                reason,
                max_attempts=10**100,
                base_delay_seconds=10**100,
                max_delay_seconds=10**100,
            )
        self.assertEqual(state["attempt"], MAX_ALLOWED_ATTEMPTS)
        self.assertEqual(state["state"], "stopped")
        self.assertIsNone(state["next_retry"])

    async def test_ready_persistence_clears_old_reason_and_locks_metadata_row(self):
        old_state = {
            "state": "retrying",
            "attempt": 1,
            "max": 4,
            "next_retry": "2026-01-01T00:00:01Z",
            "reason": {"code": "amount_not_synced"},
        }
        order = SimpleNamespace(
            id=7,
            order_no="test-order",
            metadata_json={"unrelated": "keep", PAYMENT_GUARD_METADATA_KEY: old_state},
        )
        session = _Session(order)
        ready_state = build_ready_state(old_state, amount="12.50", platform_status="待发货")

        result = await OrderService(session).update_order_payment_guard(
            "test-order",
            ready_state,
            clear_fail_reason=True,
        )
        self.assertTrue(result)
        self.assertEqual(session.commit_count, 1)
        self.assertEqual(session.rollback_count, 0)
        self.assertIsNotNone(session.statements[0]._for_update_arg)

        values = session.statements[1].compile().params
        self.assertIsNone(values["delivery_fail_reason"])
        self.assertEqual(values["metadata"]["unrelated"], "keep")
        self.assertEqual(values["metadata"][PAYMENT_GUARD_METADATA_KEY]["state"], "ready")

    async def test_stale_retry_cannot_reopen_ready_state(self):
        current = build_ready_state(None, amount="12.50", platform_status="待发货")
        order = SimpleNamespace(
            id=8,
            order_no="test-order-ready",
            metadata_json={PAYMENT_GUARD_METADATA_KEY: current},
        )
        session = _Session(order)
        stale_retry = build_retry_state(current, {"code": "amount_not_synced", "amount": "0"})

        result = await OrderService(session).update_order_payment_guard(
            "test-order-ready",
            stale_retry,
            fail_reason="stale retry reason",
        )
        self.assertTrue(result)
        values = session.statements[1].compile().params
        persisted = values["metadata"][PAYMENT_GUARD_METADATA_KEY]
        self.assertEqual(persisted["state"], "ready")
        self.assertNotIn("delivery_fail_reason", values)

    async def test_stale_ready_cannot_reopen_stopped_state(self):
        stopped = {
            "state": "stopped",
            "attempt": 2,
            "max": 4,
            "next_retry": None,
            "reason": {"code": "order_refunded", "message": "refunded"},
        }
        order = SimpleNamespace(
            id=9,
            order_no="test-order-stopped",
            metadata_json={PAYMENT_GUARD_METADATA_KEY: stopped},
            delivery_fail_reason="existing terminal reason",
        )
        session = _Session(order)
        ready = build_ready_state(None, amount="12.50", platform_status="待发货")

        result = await OrderService(session).update_order_payment_guard(
            "test-order-stopped",
            ready,
        )
        self.assertTrue(result)
        values = session.statements[1].compile().params
        persisted = values["metadata"][PAYMENT_GUARD_METADATA_KEY]
        self.assertEqual(persisted["state"], "stopped")
        self.assertEqual(persisted["reason"]["code"], "order_refunded")
        self.assertNotIn("delivery_fail_reason", values)

    async def test_duplicate_retry_events_share_one_recovery_task(self):
        handler = object.__new__(AutoDeliveryHandler)
        handler.parent = SimpleNamespace(cookie_id="test-account")
        handler._payment_retry_tasks = {}

        async def wait_forever(*_args):
            await asyncio.sleep(60)

        handler._run_payment_delivery_retry = wait_forever
        state = build_retry_state(None, {"code": "amount_not_synced", "amount": None})

        handler._schedule_payment_retry(
            "test-order-id",
            item_id="test-item",
            buyer_id="test-buyer",
            chat_id="test-chat",
            send_user_name="test-user",
            state=state,
        )
        first_task = handler._payment_retry_tasks["test-order-id"]
        handler._schedule_payment_retry(
            "test-order-id",
            item_id="test-item",
            buyer_id="test-buyer",
            chat_id="test-chat",
            send_user_name="test-user",
            state=state,
        )
        self.assertIs(handler._payment_retry_tasks["test-order-id"], first_task)
        handler._cancel_payment_retry("test-order-id")
        await asyncio.sleep(0)
        self.assertTrue(first_task.cancelled())

    @staticmethod
    def _new_flow_handler():
        handler = object.__new__(AutoDeliveryHandler)
        handler.parent = SimpleNamespace(
            cookie_id="test-account",
            ws=object(),
            is_auto_confirm_enabled=lambda: True,
        )
        handler._payment_guard_locks = defaultdict(asyncio.Lock)
        handler._payment_retry_tasks = {}
        return handler

    async def test_retry_runner_refreshes_zero_then_positive_and_delivers_once(self):
        from common.db.compat import db_manager

        handler = self._new_flow_handler()
        order = {"metadata": {}}
        initial_state = build_retry_state(
            None,
            {"code": "amount_not_synced", "amount": "0", "amount_authoritative": False},
            now=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        order["metadata"] = {PAYMENT_GUARD_METADATA_KEY: initial_state}

        refreshes = [
            {
                "amount": "0",
                "can_ship": True,
                "status_reason": "订单状态暂不可用",
                "platform_status": "待发货",
                "local_status": "pending_ship",
                "amount_authoritative": False,
            },
            {
                "amount": "12.50",
                "can_ship": True,
                "status_reason": "订单已付款，可以发货",
                "platform_status": "待发货",
                "local_status": "pending_ship",
                "amount_authoritative": True,
            },
        ]
        handler._refresh_order_payment_state = AsyncMock(side_effect=refreshes)
        persisted_states = []

        async def persist(_order_id, state, **_kwargs):
            persisted_states.append(state)
            persisted = dict(state)
            if persisted.get("state") == "retrying":
                # Make the mock retry immediately on the next runner loop.
                persisted["next_retry"] = "2020-01-01T00:00:00Z"
            order["metadata"] = {PAYMENT_GUARD_METADATA_KEY: persisted}
            return True

        handler._persist_payment_guard_state = persist
        handler._handle_auto_delivery = AsyncMock()

        with patch.object(db_manager, "get_order_by_id", return_value=order):
            with patch("app.services.xianyu.auto_delivery_handler.asyncio.sleep", new=AsyncMock()):
                await handler._run_payment_delivery_retry(
                    "test-order-race",
                    {
                        "item_id": "test-item",
                        "buyer_id": "test-buyer",
                        "chat_id": "test-chat",
                        "send_user_name": "test-user",
                    },
                    initial_state,
                )

        self.assertEqual(handler._refresh_order_payment_state.await_count, 2)
        self.assertEqual([item["amount"] for item in refreshes], ["0", "12.50"])
        self.assertEqual(persisted_states[0]["state"], "retrying")
        self.assertEqual(persisted_states[-1]["state"], "ready")
        handler._handle_auto_delivery.assert_awaited_once()
        delivery_kwargs = handler._handle_auto_delivery.await_args.kwargs
        self.assertTrue(delivery_kwargs["skip_payment_guard"])
        self.assertEqual(delivery_kwargs["override_order_id"], "test-order-race")

    async def test_retry_runner_never_delivers_refunded_or_closed_orders(self):
        from common.db.compat import db_manager

        for status_text, expected_code in (
            ("订单退款中", "order_refunded"),
            ("交易关闭", "order_closed"),
        ):
            with self.subTest(status=status_text):
                handler = self._new_flow_handler()
                order = {"metadata": {}}
                initial_state = build_retry_state(
                    None,
                    {"code": "amount_not_synced", "amount": "0", "amount_authoritative": False},
                    now=datetime(2020, 1, 1, tzinfo=timezone.utc),
                )
                order["metadata"] = {PAYMENT_GUARD_METADATA_KEY: initial_state}
                terminal_reason = classify_terminal_reason(status_reason=status_text)
                self.assertEqual(terminal_reason["code"], expected_code)
                handler._refresh_order_payment_state = AsyncMock(
                    return_value={
                        "amount": "0",
                        "can_ship": False,
                        "status_reason": status_text,
                        "platform_status": status_text,
                        "local_status": "pending_ship",
                        "terminal_reason": terminal_reason,
                    }
                )
                handler._handle_auto_delivery = AsyncMock()

                async def persist(_order_id, state, **_kwargs):
                    order["metadata"] = {PAYMENT_GUARD_METADATA_KEY: state}
                    return True

                handler._persist_payment_guard_state = persist
                with patch.object(db_manager, "get_order_by_id", return_value=order):
                    await handler._run_payment_delivery_retry(
                        "test-order-terminal",
                        {
                            "item_id": "test-item",
                            "buyer_id": "test-buyer",
                            "chat_id": "test-chat",
                            "send_user_name": "test-user",
                        },
                        initial_state,
                    )

                handler._refresh_order_payment_state.assert_awaited_once()
                handler._handle_auto_delivery.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
