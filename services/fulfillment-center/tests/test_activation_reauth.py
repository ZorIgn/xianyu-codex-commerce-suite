from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import patch


class ActivationReauthQueueTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.previous_database_path = os.environ.get("DATABASE_PATH")
        os.environ["DATABASE_PATH"] = os.path.join(self.tmp.name, "test.sqlite3")
        os.environ["DRY_RUN"] = "true"
        from app.db import init_db

        init_db()

    def tearDown(self) -> None:
        if self.previous_database_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = self.previous_database_path
        self.tmp.cleanup()

    def test_reauth_runs_before_provider_when_enabled(self) -> None:
        from app.activation import queue as queue_module
        from app.activation.queue import ActivationQueueManager
        from app.db import connect
        from app.inventory import import_cpa

        imported = import_cpa(
            {
                "email": "queue-reauth@example.com",
                "password": "pw",
                "access_token": "a",
                "refresh_token": "r",
                "id_token": "i",
            }
        )
        inventory_id = int(imported["details"][0]["inventory_id"])
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO app_settings(key, value, updated_at)
                VALUES ('reauth_before_activation', 'true', datetime('now'))
                ON CONFLICT(key) DO UPDATE SET value = 'true', updated_at = datetime('now')
                """
            )
            conn.execute(
                "UPDATE inventory_items SET status='shipped', reserved_order_id='order-reauth' WHERE id=?",
                (inventory_id,),
            )
            conn.execute(
                "INSERT INTO fulfillments(order_id, buyer_id, status, quantity) VALUES ('order-reauth', 'manual', 'account_sent', 1)"
            )
            conn.execute(
                "INSERT INTO fulfillment_items(order_id, inventory_id, status) VALUES ('order-reauth', ?, 'shipped')",
                (inventory_id,),
            )
            batch_id = int(
                conn.execute(
                    """
                    INSERT INTO activation_batches(
                        order_id, buyer_id, idempotency_key, status,
                        current_stage, quantity, manual
                    ) VALUES ('order-reauth', 'manual', 'test-reauth', 'queued', 'queued', 1, 1)
                    """
                ).lastrowid
            )
            conn.execute(
                """
                INSERT INTO activation_jobs(
                    batch_id, order_id, inventory_id, status, stage, provider
                ) VALUES (?, 'order-reauth', ?, 'queued', 'queued', 'desktop')
                """,
                (batch_id, inventory_id),
            )

        calls: list[str] = []

        def fake_reauth(value: int) -> dict[str, object]:
            calls.append("reauth")
            return {"method": "mock", "updated": True}

        async def fake_provider(self, item, stage_callback=None):
            calls.append("provider")
            return {"ok": True, "reply": "mock-ok", "stage": "completed"}

        manager = ActivationQueueManager()
        with patch.object(
            queue_module,
            "automatic_reauthorize_inventory_oauth",
            side_effect=fake_reauth,
        ):
            with patch.object(
                ActivationQueueManager,
                "_provider_result",
                new=fake_provider,
            ):
                asyncio.run(manager.process_batch(batch_id))

        with connect() as conn:
            job = dict(
                conn.execute(
                    "SELECT status, stage FROM activation_jobs WHERE batch_id=?",
                    (batch_id,),
                ).fetchone()
            )
            inventory = dict(
                conn.execute(
                    "SELECT status FROM inventory_items WHERE id=?",
                    (inventory_id,),
                ).fetchone()
            )
        self.assertEqual(calls, ["reauth", "provider"])
        self.assertEqual(job, {"status": "activated", "stage": "completed"})
        self.assertEqual(inventory["status"], "activated")


if __name__ == "__main__":
    unittest.main()