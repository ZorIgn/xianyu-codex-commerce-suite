from __future__ import annotations

import asyncio
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


class HighConcurrencyWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["DATABASE_PATH"] = os.path.join(self.tmp.name, "workflow.sqlite3")
        os.environ["DRY_RUN"] = "true"
        os.environ["LOW_STOCK_THRESHOLD"] = "0"
        from app.main import app

        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.tmp.cleanup()

    def _import_one(self, email: str = "workflow@example.com") -> int:
        result = self.client.post(
            "/inventory/import-cpa",
            json={"payload": [{"email": email, "password": "pw", "validity_status": "valid", "reset_count": 0}]},
        )
        self.assertEqual(result.status_code, 200)
        return int(result.json()["details"][0]["inventory_id"])

    def test_paid_webhook_is_durable_and_sent_without_duplicate_inventory(self) -> None:
        inventory_id = self._import_one()
        response = self.client.post(
            "/webhooks/xianyu/order-paid",
            headers={"Idempotency-Key": "paid-workflow-1"},
            json={"order_id": "paid-workflow-1", "buyer_id": "buyer", "item_id": "item", "chat_id": "chat", "account_id": "account", "quantity": 1},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["queued"])

        deadline = time.monotonic() + 3
        job = {}
        while time.monotonic() < deadline:
            job = self.client.get("/delivery/jobs/paid-workflow-1").json()
            if job.get("status") == "sent":
                break
            time.sleep(0.05)
        self.assertEqual(job.get("status"), "sent")
        self.assertEqual(job["allocated_quantity"], 1)
        self.assertEqual(job["outbox"][0]["status"], "sent")
        self.assertEqual(self.client.get("/inventory").json()[0]["id"], inventory_id)

        with self.client as client:
            duplicate = client.post(
                "/webhooks/xianyu/order-paid",
                headers={"Idempotency-Key": "paid-workflow-1"},
                json={"order_id": "paid-workflow-1", "buyer_id": "buyer", "item_id": "item", "chat_id": "chat", "account_id": "account", "quantity": 1},
            )
            self.assertEqual(duplicate.status_code, 200)
        from app.db import connect

        with connect() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM fulfillment_items WHERE order_id='paid-workflow-1'"
            ).fetchone()["n"]
        self.assertEqual(count, 1)

    def test_send_failure_retry_keeps_the_same_allocated_inventory(self) -> None:
        inventory_id = self._import_one("send-failure@example.com")
        from app.fulfillment import ship_order

        async def fail(*args, **kwargs):
            raise RuntimeError("temporary upstream failure")

        with patch("app.fulfillment.XianyuAdapter.send_message", new=AsyncMock(side_effect=fail)):
            first = asyncio.run(
                ship_order(
                    order_id="send-failure-1",
                    buyer_id="buyer",
                    quantity=1,
                    send_to_xianyu=True,
                    idempotency_key="send-failure-1",
                )
            )
            second = asyncio.run(
                ship_order(
                    order_id="send-failure-1",
                    buyer_id="buyer",
                    quantity=1,
                    send_to_xianyu=True,
                    idempotency_key="send-failure-1-retry",
                )
            )
        self.assertTrue(first["send_pending"])
        self.assertTrue(second["send_pending"])
        from app.db import connect

        with connect() as conn:
            rows = conn.execute(
                "SELECT inventory_id FROM fulfillment_items WHERE order_id='send-failure-1'"
            ).fetchall()
            item = conn.execute(
                "SELECT status FROM inventory_items WHERE id=?", (inventory_id,)
            ).fetchone()
        self.assertEqual(len(rows), 1)
        self.assertEqual(int(rows[0]["inventory_id"]), inventory_id)
        self.assertEqual(item["status"], "shipped")

    def test_quantity_reconcile_only_increases_the_target(self) -> None:
        inventory_id = self._import_one("reconcile@example.com")
        from app.delivery_queue import enqueue_delivery_job, reconcile_delivery_quantity

        with patch("app.delivery_queue.DeliveryQueueManager.start"):
            asyncio.run(
                enqueue_delivery_job(
                    order_id="reconcile-1",
                    buyer_id="buyer",
                    quantity=1,
                    send_to_xianyu=False,
                    idempotency_key="reconcile-1",
                )
            )
            job = asyncio.run(reconcile_delivery_quantity("reconcile-1", 3))
        self.assertEqual(job["requested_quantity"], 3)
        self.assertEqual(job["status"], "queued")
        self.assertEqual(inventory_id, 1)

    def test_oauth_batch_is_persisted_and_can_be_cancelled(self) -> None:
        first = self._import_one("oauth-batch-1@example.com")
        second = self._import_one("oauth-batch-2@example.com")
        from app.oauth_batch import cancel_refresh_batch, create_refresh_batch

        with patch("app.oauth_batch.OAuthBatchManager.start"):
            batch = create_refresh_batch([first, second])
        self.assertEqual(batch["total"], 2)
        self.assertEqual(len(batch["jobs"]), 2)
        cancelled = cancel_refresh_batch(int(batch["id"]))
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertTrue(all(job["status"] == "cancelled" for job in cancelled["jobs"]))

    def test_instance_bridge_paths_are_isolated_and_bad_pool_is_reported(self) -> None:
        from app.activation.desktop_provider import DesktopInstance, DesktopProvider
        from app.activation.queue import worker_status
        from app.db import connect

        one = DesktopInstance("one", "one", Path("E:/one"), Path("E:/app-one"))
        two = DesktopInstance("two", "two", Path("E:/two"), Path("E:/app-two"))
        provider = DesktopProvider()
        self.assertNotEqual(provider._bridge_root(one), provider._bridge_root(two))
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO app_settings(key, value, updated_at)
                VALUES ('desktop_instance_pool', '{bad-json', datetime('now'))
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """
            )
        status = worker_status()
        self.assertIn("instance_pool_error", status)


if __name__ == "__main__":
    unittest.main()
