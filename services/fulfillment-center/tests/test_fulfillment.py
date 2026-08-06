from __future__ import annotations

import os
import tempfile
import time
import unittest

from fastapi.testclient import TestClient


class FulfillmentFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["DATABASE_PATH"] = os.path.join(self.tmp.name, "test.sqlite3")
        os.environ["DRY_RUN"] = "true"
        os.environ["LOW_STOCK_THRESHOLD"] = "1"
        from app.main import app

        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.tmp.cleanup()

    def test_ship_quantity_then_manual_activate(self) -> None:
        imported = self.client.post(
            "/inventory/import-cpa",
            json={
                "payload": [
                    {"email": "one@example.com", "password": "secret", "validity_status": "valid", "reset_count": 0},
                    {"email": "two@example.com", "password": "secret", "validity_status": "valid", "reset_count": 0},
                ]
            },
        )
        self.assertEqual(imported.status_code, 200)
        self.assertEqual(imported.json()["created"], 2)

        shipped = self.client.post(
            "/fulfillments/ship",
            headers={"Idempotency-Key": "ship-1"},
            json={"order_id": "xy-1", "buyer_id": "buyer-1", "quantity": 2, "send_to_xianyu": False},
        )
        self.assertEqual(shipped.status_code, 200)
        self.assertEqual(shipped.json()["status"], "account_sent")
        self.assertEqual(len(shipped.json()["items"]), 2)

        inventory_id = shipped.json()["items"][0]["inventory_id"]
        activated = self.client.post(
            "/fulfillments/activate-item",
            json={"order_id": "xy-1", "inventory_id": inventory_id},
        )
        self.assertEqual(activated.status_code, 200)

        deadline = time.monotonic() + 3
        fulfillment = activated.json()
        while fulfillment["status"] != "partially_activated" and time.monotonic() < deadline:
            time.sleep(0.05)
            fulfillment = self.client.get("/fulfillments/xy-1").json()
        self.assertEqual(fulfillment["status"], "partially_activated")

        summary = self.client.get("/inventory/summary").json()
        self.assertEqual(summary["by_status"].get("activated"), 1)
        self.assertEqual(summary["by_status"].get("shipped"), 1)


if __name__ == "__main__":
    unittest.main()
