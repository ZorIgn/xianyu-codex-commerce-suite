from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


class OAuthRetryAndPrivacyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["DATABASE_PATH"] = os.path.join(self.tmp.name, "oauth.sqlite3")
        os.environ["DRY_RUN"] = "true"
        os.environ["OAUTH_REAUTH_RETRY_LIMIT"] = "3"
        from app.main import app

        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.tmp.cleanup()

    def test_transient_oauth_failure_retries_until_third_attempt(self) -> None:
        from app.oauth_reauth import OAuthReauthError, automatic_reauthorize_inventory_oauth_retry

        failures = [OAuthReauthError("network timeout"), OAuthReauthError("browser temporarily unavailable")]
        with patch(
            "app.oauth_reauth.automatic_reauthorize_inventory_oauth",
            side_effect=[*failures, {"updated": True}],
        ) as run, patch("app.oauth_reauth.get_setting", return_value="0,0,0"), patch(
            "app.oauth_reauth.time.sleep"
        ):
            result = automatic_reauthorize_inventory_oauth_retry(42)
        self.assertTrue(result["updated"])
        self.assertEqual(run.call_count, 3)

    def test_password_error_is_not_retried(self) -> None:
        from app.oauth_reauth import OAuthReauthError, automatic_reauthorize_inventory_oauth_retry

        with patch(
            "app.oauth_reauth.automatic_reauthorize_inventory_oauth",
            side_effect=OAuthReauthError("password incorrect"),
        ) as run, patch("app.oauth_reauth.get_setting", return_value="0,0,0"), patch(
            "app.oauth_reauth.time.sleep"
        ):
            with self.assertRaises(OAuthReauthError):
                automatic_reauthorize_inventory_oauth_retry(42)
        self.assertEqual(run.call_count, 1)

    def test_inventory_and_oauth_batch_responses_do_not_expose_secrets(self) -> None:
        imported = self.client.post(
            "/inventory/import-cpa",
            json={
                "payload": [{
                    "email": "privacy@example.com",
                    "password": "do-not-return",
                    "access_token": "access-secret",
                    "refresh_token": "refresh-secret",
                    "id_token": "id-secret",
                }],
            },
        )
        self.assertEqual(imported.status_code, 200)
        inventory = self.client.get("/inventory").json()[0]
        for key in ("password", "primary_token", "session_token", "refresh_token", "source_payload"):
            self.assertNotIn(key, inventory)
        with patch("app.oauth_batch.OAuthBatchManager.start"):
            batch = self.client.post(
                "/oauth/refresh-batches",
                json={"inventory_ids": [inventory["id"]]},
            )
        self.assertEqual(batch.status_code, 200)
        body = batch.json()
        serialized = str(body)
        for secret in ("do-not-return", "access-secret", "refresh-secret", "id-secret"):
            self.assertNotIn(secret, serialized)


if __name__ == "__main__":
    unittest.main()
