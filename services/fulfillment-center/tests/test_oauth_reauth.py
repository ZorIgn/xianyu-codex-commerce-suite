from __future__ import annotations

import json
import os
import tempfile
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class OAuthReauthTest(unittest.TestCase):
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

    def _inventory_id(self) -> int:
        from app.db import connect

        with connect() as conn:
            row = conn.execute(
                "SELECT id FROM inventory_items WHERE email = ?",
                ("refresh@example.com",),
            ).fetchone()
        return int(row["id"])

    def test_start_reauth_reuses_inventory_and_redacts_list_response(self) -> None:
        from app.inventory import import_cpa, list_inventory
        from app.oauth_reauth import create_reauth_session

        import_cpa(
            {
                "email": "refresh@example.com",
                "credentials": {
                    "access_token": "access-before",
                    "refresh_token": "refresh-before",
                    "id_token": "id-before",
                },
            }
        )
        inventory_id = self._inventory_id()
        session = create_reauth_session(inventory_id)

        self.assertTrue(session["auth_url"].startswith("https://auth.openai.com/"))
        self.assertNotIn("access-before", session["auth_url"])
        self.assertIn("session_id", session)

        listed = list_inventory()
        self.assertEqual(len(listed), 1)
        self.assertNotIn("primary_token", listed[0])
        self.assertNotIn("refresh_token", listed[0])
        self.assertNotIn("source_payload", listed[0])
        self.assertTrue(listed[0]["credential_fields_present"]["refresh_token"])

    def test_import_oauth_only_replaces_credentials_and_preserves_stock_state(self) -> None:
        from app.db import connect
        from app.inventory import import_cpa
        from app.oauth_reauth import import_oauth_payload

        import_cpa(
            {
                "email": "refresh@example.com",
                "access_token": "old-access",
                "refresh_token": "old-refresh",
                "id_token": "old-id",
            }
        )
        inventory_id = self._inventory_id()
        with connect() as conn:
            conn.execute(
                "UPDATE inventory_items SET status = 'shipped', reserved_order_id = 'order-1' WHERE id = ?",
                (inventory_id,),
            )

        result = import_oauth_payload(
            inventory_id,
            {
                "accounts": [
                    {
                        "name": "refresh@example.com",
                        "credentials": {
                            "access_token": "new-access",
                            "refresh_token": "new-refresh",
                            "id_token": "new-id",
                            "account_id": "account-1",
                        },
                    }
                ]
            },
        )
        self.assertTrue(result["updated"])

        with connect() as conn:
            row = dict(
                conn.execute(
                    "SELECT * FROM inventory_items WHERE id = ?", (inventory_id,)
                ).fetchone()
            )
        self.assertEqual(row["status"], "shipped")
        self.assertEqual(row["reserved_order_id"], "order-1")
        self.assertEqual(row["primary_token"], "new-access")
        self.assertEqual(row["refresh_token"], "new-refresh")
        self.assertEqual(json.loads(row["source_payload"])["credentials"]["id_token"], "new-id")



    def test_automatic_worker_persists_without_forwarding_mailbox_tokens(self) -> None:
        from app.db import connect
        from app.inventory import import_cpa
        from app.oauth_reauth import AUTO_RESULT_PREFIX, automatic_reauthorize_inventory_oauth

        import_cpa(
            {
                "email": "automatic@example.com",
                "password": "openai-password",
                "access_token": "old-access",
                "refresh_token": "old-refresh",
            }
        )
        with connect() as conn:
            inventory_id = int(
                conn.execute(
                    "SELECT id FROM inventory_items WHERE email = ?",
                    ("automatic@example.com",),
                ).fetchone()["id"]
            )
            conn.execute(
                "UPDATE inventory_items SET status = 'shipped', reserved_order_id = 'order-auto' WHERE id = ?",
                (inventory_id,),
            )

        class FakeProcess:
            def __init__(self):
                self.input_text = ""

            def communicate(self, _input=None, timeout=None):
                self.input_text = _input or ""
                payload = {
                    "ok": True,
                    "email": "automatic@example.com",
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                    "id_token": "new-id",
                }
                return AUTO_RESULT_PREFIX + json.dumps(payload) + "\n", ""

        process = FakeProcess()
        settings = SimpleNamespace(
            cockpit_python=Path(sys.executable),
            abai_project_root=Path(self.tmp.name),
            oauth_mailbox_provider="cfworker_admin_api",
            oauth_browser_mode="camoufox_headless",
            oauth_browser_timeout_seconds=30,
        )
        with patch("app.oauth_reauth.get_settings", return_value=settings):
            with patch("app.oauth_reauth.subprocess.Popen", return_value=process) as popen:
                result = automatic_reauthorize_inventory_oauth(inventory_id)

        request = json.loads(process.input_text)
        self.assertEqual(request["email"], "automatic@example.com")
        self.assertEqual(request["password"], "openai-password")
        self.assertNotIn("mailbox_provider", request)
        self.assertNotIn("mailbox_refresh_token", request)
        self.assertEqual(result["method"], "cockpit_local_auto_oauth")
        self.assertIsNotNone(popen.call_args)

        with connect() as conn:
            row = dict(
                conn.execute(
                    "SELECT * FROM inventory_items WHERE id = ?", (inventory_id,)
                ).fetchone()
            )
        self.assertEqual(row["status"], "shipped")
        self.assertEqual(row["reserved_order_id"], "order-auto")
        self.assertEqual(row["primary_token"], "new-access")
        self.assertEqual(row["refresh_token"], "new-refresh")
if __name__ == "__main__":
    unittest.main()
