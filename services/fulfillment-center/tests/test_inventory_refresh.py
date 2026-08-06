from __future__ import annotations

import json
import os
import tempfile
import unittest


class InventoryRefreshAndQueueTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.previous_database_path = os.environ.get("DATABASE_PATH")
        os.environ["DATABASE_PATH"] = os.path.join(self.tmp.name, "test.sqlite3")
        os.environ["DRY_RUN"] = "true"

    def tearDown(self) -> None:
        if self.previous_database_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = self.previous_database_path
        self.tmp.cleanup()

    def test_duplicate_cpa_import_refreshes_credentials_without_moving_stock(self) -> None:
        from app.db import connect
        from app.inventory import import_cpa

        first = import_cpa(
            {
                "email": "stock@example.com",
                "account_id": "account-1",
                "access_token": "old-access",
                "expired": "2026-08-10T00:00:00Z",
            }
        )
        self.assertEqual(first["created"], 1)
        with connect() as conn:
            row = conn.execute(
                "SELECT id FROM inventory_items WHERE email = ?",
                ("stock@example.com",),
            ).fetchone()
            inventory_id = int(row["id"])
            conn.execute(
                """
                UPDATE inventory_items
                SET status = 'shipped', reserved_order_id = 'order-1'
                WHERE id = ?
                """,
                (inventory_id,),
            )

        refreshed = import_cpa(
            {
                "name": "stock@example.com",
                "platform": "openai",
                "type": "oauth",
                "credentials": {
                    "email": "stock@example.com",
                    "chatgpt_account_id": "account-1",
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                    "id_token": "new-id",
                },
            }
        )
        self.assertEqual(refreshed["created"], 0)
        self.assertEqual(refreshed["updated"], 1)

        with connect() as conn:
            rows = conn.execute(
                "SELECT * FROM inventory_items WHERE lower(email) = lower(?)",
                ("stock@example.com",),
            ).fetchall()
        self.assertEqual(len(rows), 1)
        row = dict(rows[0])
        self.assertEqual(row["id"], inventory_id)
        self.assertEqual(row["status"], "shipped")
        self.assertEqual(row["reserved_order_id"], "order-1")
        self.assertEqual(row["primary_token"], "new-access")
        self.assertEqual(row["refresh_token"], "new-refresh")
        source = json.loads(row["source_payload"])
        self.assertEqual(source["credentials"]["id_token"], "new-id")

        unchanged = import_cpa(source)
        self.assertEqual(unchanged["created"], 0)
        self.assertEqual(unchanged["updated"], 0)
        self.assertEqual(unchanged["skipped"], 1)
        self.assertEqual(unchanged["details"][0]["action"], "skipped")

    def test_only_one_activation_worker_can_lead(self) -> None:
        from app.activation.queue import ActivationQueueManager

        first = ActivationQueueManager()
        second = ActivationQueueManager()
        try:
            self.assertTrue(first._acquire_worker_lock())
            self.assertFalse(second._acquire_worker_lock())
            first._release_worker_lock()
            self.assertTrue(second._acquire_worker_lock())
        finally:
            first._release_worker_lock()
            second._release_worker_lock()

    def test_expired_post_send_job_requires_manual_review(self) -> None:
        from app.activation.queue import ActivationQueueManager
        from app.db import connect
        from app.inventory import import_cpa

        import_cpa(
            {
                "email": "ambiguous@example.com",
                "account_id": "ambiguous-1",
                "access_token": "access",
            }
        )
        with connect() as conn:
            inventory_id = int(
                conn.execute(
                    "SELECT id FROM inventory_items WHERE email = ?",
                    ("ambiguous@example.com",),
                ).fetchone()["id"]
            )
            conn.execute(
                """
                UPDATE inventory_items
                SET status = 'activating',
                    reserved_order_id = 'order-ambiguous'
                WHERE id = ?
                """,
                (inventory_id,),
            )
            conn.execute(
                """
                INSERT INTO fulfillment_items(order_id, inventory_id, status)
                VALUES ('order-ambiguous', ?, 'activating')
                """,
                (inventory_id,),
            )
            cursor = conn.execute(
                """
                INSERT INTO activation_batches(
                    order_id, idempotency_key, status, current_stage,
                    worker_owner, lease_expires_at
                )
                VALUES (
                    'order-ambiguous', 'recover-1', 'activating',
                    'sending', 'dead-worker', '2000-01-01 00:00:00'
                )
                """
            )
            batch_id = int(cursor.lastrowid)
            conn.execute(
                """
                INSERT INTO activation_jobs(
                    batch_id, order_id, inventory_id, status, stage,
                    lease_owner, lease_expires_at
                )
                VALUES (
                    ?, 'order-ambiguous', ?, 'sending', 'sending',
                    'dead-worker', '2000-01-01 00:00:00'
                )
                """,
                (batch_id, inventory_id),
            )

        ActivationQueueManager()._recover_expired()

        with connect() as conn:
            job = conn.execute(
                "SELECT status, stage, error_message FROM activation_jobs"
            ).fetchone()
            inventory = conn.execute(
                "SELECT status, activation_error FROM inventory_items WHERE id = ?",
                (inventory_id,),
            ).fetchone()
            batch = conn.execute(
                "SELECT status FROM activation_batches WHERE id = ?",
                (batch_id,),
            ).fetchone()
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["stage"], "manual_review")
        self.assertIn("人工确认", job["error_message"])
        self.assertEqual(inventory["status"], "activation_failed")
        self.assertEqual(batch["status"], "queued")
    def test_delete_inventory_cleans_terminal_links(self) -> None:
        from app.db import connect
        from app.inventory import delete_inventory_item, import_cpa

        import_cpa(
            {
                "email": "delete@example.com",
                "account_id": "delete-1",
                "access_token": "access",
            }
        )
        with connect() as conn:
            inventory_id = int(
                conn.execute(
                    "SELECT id FROM inventory_items WHERE email = ?",
                    ("delete@example.com",),
                ).fetchone()["id"]
            )
            conn.execute(
                """
                INSERT INTO fulfillments(
                    order_id, buyer_id, status, inventory_id
                )
                VALUES ('delete-order', 'manual', 'activation_failed', ?)
                """,
                (inventory_id,),
            )
            conn.execute(
                """
                INSERT INTO fulfillment_items(
                    order_id, inventory_id, status
                )
                VALUES ('delete-order', ?, 'activation_failed')
                """,
                (inventory_id,),
            )
            batch_id = int(
                conn.execute(
                    """
                    INSERT INTO activation_batches(
                        order_id, idempotency_key, status
                    )
                    VALUES (
                        'delete-order', 'delete-batch', 'failed'
                    )
                    """
                ).lastrowid
            )
            conn.execute(
                """
                INSERT INTO activation_jobs(
                    batch_id, order_id, inventory_id, status, stage
                )
                VALUES (
                    ?, 'delete-order', ?, 'failed', 'failed'
                )
                """,
                (batch_id, inventory_id),
            )

        result = delete_inventory_item(inventory_id)
        self.assertTrue(result["deleted"])
        self.assertEqual(result["removed_fulfillment_items"], 1)
        self.assertEqual(result["removed_activation_jobs"], 1)
        self.assertEqual(result["removed_activation_batches"], 1)

        with connect() as conn:
            self.assertIsNone(
                conn.execute(
                    "SELECT 1 FROM inventory_items WHERE id = ?",
                    (inventory_id,),
                ).fetchone()
            )
            self.assertIsNone(
                conn.execute(
                    "SELECT 1 FROM activation_jobs WHERE inventory_id = ?",
                    (inventory_id,),
                ).fetchone()
            )
            fulfillment = conn.execute(
                """
                SELECT inventory_id
                FROM fulfillments
                WHERE order_id = 'delete-order'
                """
            ).fetchone()
            self.assertIsNone(fulfillment["inventory_id"])

    def test_delete_inventory_rejects_active_job(self) -> None:
        from app.db import connect
        from app.inventory import (
            InventoryDeleteBlocked,
            delete_inventory_item,
            import_cpa,
        )

        import_cpa(
            {
                "email": "active@example.com",
                "account_id": "active-1",
                "access_token": "access",
            }
        )
        with connect() as conn:
            inventory_id = int(
                conn.execute(
                    "SELECT id FROM inventory_items WHERE email = ?",
                    ("active@example.com",),
                ).fetchone()["id"]
            )
            batch_id = int(
                conn.execute(
                    """
                    INSERT INTO activation_batches(
                        order_id, idempotency_key, status
                    )
                    VALUES ('active-order', 'active-batch', 'queued')
                    """
                ).lastrowid
            )
            conn.execute(
                """
                INSERT INTO activation_jobs(
                    batch_id, order_id, inventory_id, status, stage
                )
                VALUES (
                    ?, 'active-order', ?, 'queued', 'queued'
                )
                """,
                (batch_id, inventory_id),
            )

        with self.assertRaises(InventoryDeleteBlocked):
            delete_inventory_item(inventory_id)

        with connect() as conn:
            self.assertIsNotNone(
                conn.execute(
                    "SELECT 1 FROM inventory_items WHERE id = ?",
                    (inventory_id,),
                ).fetchone()
            )

if __name__ == "__main__":
    unittest.main()