from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


class ReleaseIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["DATABASE_PATH"] = os.path.join(self.tmp.name, "release.sqlite3")
        os.environ["DRY_RUN"] = "true"
        os.environ["LOW_STOCK_THRESHOLD"] = "0"
        os.environ["DELIVERY_RETRY_BASE_SECONDS"] = "0"
        from app.main import app

        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.tmp.cleanup()
        os.environ["DRY_RUN"] = "true"

    def _import(self, count: int = 2) -> None:
        payload = [
            {
                "email": f"release-{index}@example.com",
                "password": "not-returned",
                "validity_status": "valid",
                "reset_count": 0,
            }
            for index in range(count)
        ]
        response = self.client.post("/inventory/import-cpa", json={"payload": payload})
        self.assertEqual(response.status_code, 200)

    def _wait_for_job(self, order_id: str, allocated: int) -> dict:
        deadline = time.monotonic() + 4
        latest: dict = {}
        while time.monotonic() < deadline:
            latest = self.client.get(f"/delivery/jobs/{order_id}").json()
            if latest.get("allocated_quantity") == allocated and latest.get("status") == "sent":
                return latest
            time.sleep(0.05)
        return latest

    def test_real_paid_webhook_carries_metadata_and_reconcile_after_shipped(self) -> None:
        self._import(2)
        paid = self.client.post(
            "/webhooks/xianyu/order-paid",
            headers={"Idempotency-Key": "release-paid-1"},
            json={
                "order_id": "release-paid-1",
                "buyer_id": "buyer-release",
                "item_id": "item-release",
                "chat_id": "chat-release",
                "account_id": "account-release",
                "quantity": 1,
            },
        )
        self.assertEqual(paid.status_code, 200)
        job = self._wait_for_job("release-paid-1", 1)
        self.assertEqual(job.get("status"), "sent")
        self.assertEqual(job.get("chat_id"), "chat-release")
        self.assertEqual(job.get("account_id"), "account-release")

        reconciled = self.client.post(
            "/delivery/jobs/release-paid-1/reconcile",
            json={"quantity": 2},
        )
        self.assertEqual(reconciled.status_code, 200)
        final_job = self._wait_for_job("release-paid-1", 2)
        self.assertEqual(final_job.get("allocated_quantity"), 2)
        self.assertEqual(final_job.get("status"), "sent")
        fulfillment = self.client.get("/fulfillments/release-paid-1").json()
        self.assertEqual(fulfillment.get("status"), "account_sent")
        self.assertEqual(len(fulfillment.get("items") or []), 2)

    def test_outbox_failure_sets_send_pending_without_reallocating(self) -> None:
        self._import(1)
        from app.delivery_queue import DeliveryQueueManager, enqueue_delivery_job, get_delivery_job

        with patch("app.delivery_queue.DeliveryQueueManager.start"):
            queued = asyncio.run(
                enqueue_delivery_job(
                    order_id="release-failure-1",
                    buyer_id="buyer-release",
                    chat_id="chat-release",
                    account_id="account-release",
                    item_id="item-release",
                    quantity=1,
                    send_to_xianyu=True,
                    idempotency_key="release-failure-1",
                )
            )
        manager = DeliveryQueueManager()
        with patch(
            "app.delivery_queue.XianyuAdapter.send_message",
            new=AsyncMock(side_effect=RuntimeError("success:false from internal API")),
        ):
            asyncio.run(manager._process_job(queued))

        job = get_delivery_job("release-failure-1")
        self.assertIsNotNone(job)
        self.assertEqual(job["status"], "sending")
        self.assertEqual(job["allocated_quantity"], 1)
        self.assertEqual(job["outbox"][0]["status"], "queued")
        fulfillment = self.client.get("/fulfillments/release-failure-1").json()
        self.assertEqual(fulfillment.get("status"), "send_pending")
        self.assertEqual(len(fulfillment.get("items") or []), 1)

    def test_xianyu_adapter_rejects_http_200_success_false(self) -> None:
        from app.adapters import XianyuAdapter

        class FakeResponse:
            status_code = 200
            headers = {"content-type": "application/json"}
            text = json.dumps({"success": False, "code": 500, "message": "internal rejected"})

            def json(self):
                return json.loads(self.text)

            def raise_for_status(self):
                return None

        class FakeClient:
            def __init__(self, *args, **kwargs):
                self.payload = None

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def post(self, url, headers=None, json=None):
                self.payload = json
                return FakeResponse()

        fake_client = FakeClient()
        os.environ["DRY_RUN"] = "false"
        os.environ["XIANYU_BASE_URL"] = "http://xianyu.internal"
        with patch("app.adapters.httpx.AsyncClient", return_value=fake_client):
            with self.assertRaises(RuntimeError):
                asyncio.run(
                    XianyuAdapter().send_message(
                        "buyer-release",
                        "release-adapter-1",
                        "delivery text",
                        chat_id="chat-release",
                        account_id="account-release",
                    )
                )
        self.assertEqual(fake_client.payload["chat_id"], "chat-release")
        self.assertEqual(fake_client.payload["account_id"], "account-release")
        self.assertEqual(fake_client.payload["order_id"], "release-adapter-1")


if __name__ == "__main__":
    unittest.main()
