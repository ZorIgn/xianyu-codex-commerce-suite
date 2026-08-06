from __future__ import annotations

import os
import tempfile
import unittest


class ActivationQueueCancelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["DATABASE_PATH"] = os.path.join(self.tmp.name, "queue.sqlite3")
        os.environ["DRY_RUN"] = "true"
        from app.db import init_db

        init_db()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _seed(self, status: str = "queued") -> int:
        from app.db import connect

        with connect() as conn:
            inventory_id = int(
                conn.execute(
                    "INSERT INTO inventory_items(email, status, reserved_order_id) VALUES (?, 'shipped', 'order-1')",
                    ("queue@example.com",),
                ).lastrowid
            )
            conn.execute(
                "INSERT INTO fulfillments(order_id, status, quantity) VALUES ('order-1', 'activation_queued', 1)"
            )
            conn.execute(
                "INSERT INTO fulfillment_items(order_id, inventory_id, status) VALUES ('order-1', ?, 'shipped')",
                (inventory_id,),
            )
            batch_id = int(
                conn.execute(
                    "INSERT INTO activation_batches(order_id, idempotency_key, status, current_stage) VALUES ('order-1', 'cancel-test', ?, ?)",
                    (status, "queued" if status == "queued" else "switching_account"),
                ).lastrowid
            )
            conn.execute(
                """
                INSERT INTO activation_jobs(
                    batch_id, order_id, inventory_id, status, stage, started_at
                ) VALUES (?, 'order-1', ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    inventory_id,
                    "queued" if status == "queued" else "switching_account",
                    "queued" if status == "queued" else "switching_account",
                    None if status == "queued" else "2026-01-01 00:00:00",
                ),
            )
        return batch_id

    def test_cancel_queued_batch_keeps_inventory_shipped(self) -> None:
        from app.activation.queue import cancel_activation_batch, list_activation_queue
        from app.db import connect

        batch_id = self._seed("queued")
        result = cancel_activation_batch(batch_id)
        self.assertTrue(result["cancelled"])
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(result["jobs"][0]["status"], "cancelled")
        self.assertEqual(list_activation_queue(), [])

        with connect() as conn:
            inventory = conn.execute(
                "SELECT status FROM inventory_items WHERE email='queue@example.com'"
            ).fetchone()
            fulfillment = conn.execute(
                "SELECT status FROM fulfillments WHERE order_id='order-1'"
            ).fetchone()
        self.assertEqual(inventory["status"], "shipped")
        self.assertEqual(fulfillment["status"], "account_sent")

    def test_cannot_cancel_started_batch(self) -> None:
        from app.activation.queue import ActivationQueueConflict, cancel_activation_batch

        batch_id = self._seed("activating")
        with self.assertRaises(ActivationQueueConflict):
            cancel_activation_batch(batch_id)


if __name__ == "__main__":
    unittest.main()