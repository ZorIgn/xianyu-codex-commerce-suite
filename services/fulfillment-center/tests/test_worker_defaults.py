from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class WorkerDefaultsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.previous_database_path = os.environ.get("DATABASE_PATH")
        self.previous_activation_workers = os.environ.get("ACTIVATION_WORKER_COUNT")
        self.previous_delivery_workers = os.environ.get("DELIVERY_WORKER_COUNT")
        os.environ["DATABASE_PATH"] = os.path.join(self.tmp.name, "workers.sqlite3")
        os.environ.pop("ACTIVATION_WORKER_COUNT", None)
        os.environ.pop("DELIVERY_WORKER_COUNT", None)

    def tearDown(self) -> None:
        if self.previous_database_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = self.previous_database_path
        if self.previous_activation_workers is None:
            os.environ.pop("ACTIVATION_WORKER_COUNT", None)
        else:
            os.environ["ACTIVATION_WORKER_COUNT"] = self.previous_activation_workers
        if self.previous_delivery_workers is None:
            os.environ.pop("DELIVERY_WORKER_COUNT", None)
        else:
            os.environ["DELIVERY_WORKER_COUNT"] = self.previous_delivery_workers
        self.tmp.cleanup()

    def test_new_install_defaults_are_single_worker_across_runtime_and_ui(self) -> None:
        from app.activation.queue import _setting_int
        from app.config import get_settings
        from app.db import connect, init_db
        from app.delivery_queue import _int_setting
        from app.settings_store import get_all_settings

        init_db()

        self.assertEqual(get_settings().activation_worker_count, 1)
        self.assertEqual(_setting_int("activation_worker_count", 1), 1)
        self.assertEqual(_int_setting("delivery_worker_count", 1), 1)
        self.assertEqual(get_all_settings()["activation_worker_count"], "1")
        self.assertEqual(get_all_settings()["delivery_worker_count"], "1")

        with connect() as conn:
            rows = conn.execute(
                "SELECT key, value FROM app_settings WHERE key IN (?, ?)",
                ("activation_worker_count", "delivery_worker_count"),
            ).fetchall()
        self.assertEqual(
            {row["key"]: row["value"] for row in rows},
            {"activation_worker_count": "1", "delivery_worker_count": "1"},
        )

        root = Path(__file__).resolve().parents[1]
        env_example = (root / ".env.example").read_text(encoding="utf-8")
        config = (root / "app" / "config.py").read_text(encoding="utf-8")
        database = (root / "app" / "db.py").read_text(encoding="utf-8")
        delivery = (root / "app" / "delivery_queue.py").read_text(encoding="utf-8")
        html = (root / "app" / "static" / "index.html").read_text(encoding="utf-8")
        javascript = (root / "app" / "static" / "app.js").read_text(encoding="utf-8")
        oauth_batch = (root / "app" / "oauth_batch.py").read_text(encoding="utf-8")

        self.assertIn("ACTIVATION_WORKER_COUNT=1", env_example)
        self.assertIn("DELIVERY_WORKER_COUNT=1", env_example)
        self.assertIn('ACTIVATION_WORKER_COUNT", "1"', config)
        self.assertIn('"activation_worker_count": "1"', database)
        self.assertIn('"delivery_worker_count": "1"', database)
        self.assertIn('_int_setting("delivery_worker_count", 1)', delivery)
        self.assertIn('id="activationWorkerCount" type="number" min="1" max="16" value="1"', html)
        self.assertIn('data.activation_worker_count || "1"', javascript)
        self.assertIn('$("activationWorkerCount").value || "1"', javascript)
        self.assertIn('"browser_concurrency": 1', oauth_batch)

    def test_explicit_worker_counts_can_still_be_increased(self) -> None:
        from app.activation.queue import _setting_int
        from app.db import init_db
        from app.delivery_queue import _int_setting
        from app.settings_store import update_settings

        init_db()
        update_settings({"activation_worker_count": "4", "delivery_worker_count": "5"})

        self.assertEqual(_setting_int("activation_worker_count", 1), 4)
        self.assertEqual(_int_setting("delivery_worker_count", 1), 5)


if __name__ == "__main__":
    unittest.main()
