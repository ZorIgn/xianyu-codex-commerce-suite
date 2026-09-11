from __future__ import annotations

import asyncio
import base64
import json
import os
import tempfile
import time
import unittest


def _jwt(claims: dict[str, object]) -> str:
    def encode(value: object) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return f"{encode({'alg': 'none', 'typ': 'JWT'})}.{encode(claims)}.signature"


class CpaActivationEligibilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.previous_database_path = os.environ.get("DATABASE_PATH")
        self.previous_dry_run = os.environ.get("DRY_RUN")
        self.previous_provider = os.environ.get("ACTIVATION_PROVIDER")
        os.environ["DATABASE_PATH"] = os.path.join(self.tmp.name, "test.sqlite3")
        os.environ["DRY_RUN"] = "true"
        os.environ["ACTIVATION_PROVIDER"] = "ws"
        from app.db import init_db

        init_db()

    def tearDown(self) -> None:
        if self.previous_database_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = self.previous_database_path
        if self.previous_dry_run is None:
            os.environ.pop("DRY_RUN", None)
        else:
            os.environ["DRY_RUN"] = self.previous_dry_run
        if self.previous_provider is None:
            os.environ.pop("ACTIVATION_PROVIDER", None)
        else:
            os.environ["ACTIVATION_PROVIDER"] = self.previous_provider
        self.tmp.cleanup()

    def test_claims_fill_new_standard_fields_and_override_old_display_state(self) -> None:
        from app.db import connect
        from app.inventory import import_cpa, list_inventory, normalize_account

        token = _jwt(
            {
                "https://api.openai.com/auth": {
                    "chatgpt_account_id": "claims-account-1",
                    "expired": False,
                },
                "https://api.openai.com/profile": {
                    "email": "Claims@Example.com",
                },
                "exp": int(time.time()) + 3600,
            }
        )
        normalized = normalize_account(
            {
                "access_token": token,
                "validity_status": "unknown",
                "display_status": "not_available",
            }
        )
        self.assertEqual(normalized["account_id"], "claims-account-1")
        self.assertEqual(normalized["email"], "claims@example.com")
        self.assertTrue(normalized["expires_at"])
        self.assertEqual(normalized["validity_status"], "valid")

        result = import_cpa(
            {
                "access_token": token,
                "validity_status": "unknown",
                "display_status": "not_available",
            }
        )
        self.assertEqual(result["created"], 1)
        self.assertTrue(result["details"][0]["eligible"])
        self.assertTrue(result["details"][0]["activation_eligible"])

        with connect() as conn:
            row = dict(conn.execute("SELECT * FROM inventory_items").fetchone())
        self.assertEqual(row["account_id"], "claims-account-1")
        self.assertEqual(row["email"], "claims@example.com")
        self.assertTrue(row["expires_at"])

        listed = list_inventory()
        self.assertEqual(listed[0]["account_id"], "claims-account-1")
        self.assertEqual(listed[0]["email"], "claims@example.com")
        self.assertTrue(listed[0]["eligible"])
        self.assertNotIn("primary_token", listed[0])

    def test_known_platform_aliases_are_reservable_and_unknown_is_preserved(self) -> None:
        from app.inventory import import_cpa, normalize_account, reserve_many

        for alias in ("openai", "codex", "openai-codex", "openai_codex"):
            normalized = normalize_account(
                {
                    "platform": alias,
                    "access_token": _jwt(
                        {
                            "account_id": f"{alias}-account",
                            "email": f"{alias}@example.com",
                            "exp": int(time.time()) + 3600,
                        }
                    ),
                }
            )
            self.assertEqual(normalized["platform"], "chatgpt")

        unknown = normalize_account(
            {
                "platform": "custom-cpa-provider",
                "email": "custom@example.com",
                "password": "pw",
            }
        )
        self.assertEqual(unknown["platform"], "custom-cpa-provider")

        imported = import_cpa(
            {
                "platform": "openai",
                "access_token": _jwt(
                    {
                        "account_id": "openai-reservable-account",
                        "email": "openai-reservable@example.com",
                        "exp": int(time.time()) + 3600,
                    }
                ),
            }
        )
        self.assertTrue(imported["details"][0]["eligible"])
        reserved = reserve_many("openai-alias-order", 1, platform="openai")
        self.assertEqual(reserved[0]["account_id"], "openai-reservable-account")

    def test_old_row_hydration_recovers_claims_for_shipping(self) -> None:
        from app.db import connect
        from app.inventory import list_inventory, reserve_many

        token = _jwt(
            {
                "account_id": "old-row-account",
                "email": "OldRow@Example.com",
                "exp": int(time.time()) + 3600,
            }
        )
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO inventory_items(
                    external_id, platform, email, primary_token, validity_status,
                    display_status, source_payload
                ) VALUES (?, 'openai', '', ?, 'unknown', 'not_available', ?)
                """,
                (
                    "old-row-seed",
                    token,
                    json.dumps({"access_token": token}),
                ),
            )

        listed = list_inventory()
        self.assertEqual(listed[0]["account_id"], "old-row-account")
        self.assertEqual(listed[0]["email"], "oldrow@example.com")
        self.assertTrue(listed[0]["eligible"])
        reserved = reserve_many("old-row-order", 1)
        self.assertEqual(reserved[0]["account_id"], "old-row-account")
        self.assertEqual(reserved[0]["email"], "oldrow@example.com")

    def test_missing_account_is_importable_but_cannot_ship_or_activate(self) -> None:
        from app.fulfillment import activate_inventory_item
        from app.inventory import import_cpa, list_inventory, reserve_many

        token = _jwt(
            {
                "email": "missing-account@example.com",
                "exp": int(time.time()) + 3600,
            }
        )
        result = import_cpa({"access_token": token})
        detail = result["details"][0]
        self.assertFalse(detail["eligible"])
        self.assertEqual(detail["eligible_reason"], "missing_account_id")
        self.assertFalse(detail["activation_eligible"])
        self.assertEqual(detail["activation_eligible_reason"], "missing_account_id")

        listed = list_inventory()
        self.assertEqual(listed[0]["email"], "missing-account@example.com")
        self.assertFalse(listed[0]["eligible"])
        self.assertEqual(listed[0]["eligible_reason"], "missing_account_id")
        self.assertFalse(listed[0]["activation_eligible"])
        self.assertEqual(listed[0]["activation_eligible_reason"], "missing_account_id")
        with self.assertRaisesRegex(RuntimeError, "missing_account_id"):
            reserve_many("missing-account-order", 1)
        with self.assertRaisesRegex(RuntimeError, "missing_account_id"):
            asyncio.run(activate_inventory_item("missing-account-activate", listed[0]["id"]))

    def test_ws_provider_rejects_missing_account_before_network_activation(self) -> None:
        from app.activation.codex_ws_provider import CodexWsProvider

        os.environ["DRY_RUN"] = "false"
        result = asyncio.run(
            CodexWsProvider().activate(
                {
                    "email": "ws-missing-account@example.com",
                    "primary_token": "opaque-access-token",
                }
            )
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "ws_ineligible")
        self.assertIn("missing_account_id", result["error"])

    def test_expired_token_can_activate_but_cannot_ship(self) -> None:
        from app.inventory import import_cpa

        expired = import_cpa(
            {
                "access_token": _jwt(
                    {
                        "account_id": "expired-account",
                        "email": "expired@example.com",
                        "exp": int(time.time()) - 60,
                    }
                )
            }
        )
        self.assertTrue(expired["details"][0]["activation_eligible"])
        self.assertEqual(expired["details"][0]["activation_eligible_reason"], "ok")
        self.assertFalse(expired["details"][0]["eligible"])
        self.assertEqual(expired["details"][0]["eligible_reason"], "token_expired")

    def test_expired_id_token_and_stored_markers_allow_all_activation_providers(self) -> None:
        from app.inventory import activation_eligibility, desktop_oauth_status, normalize_account

        now = int(time.time())
        item = normalize_account(
            {
                "access_token": _jwt(
                    {"account_id": "id-expired-account", "email": "id-expired@example.com", "exp": now + 86400}
                ),
                "id_token": _jwt({"exp": now - 60}),
                "refresh_token": "test-refresh-token",
            }
        )
        self.assertEqual(item["validity_status"], "expired")
        item["lifecycle_status"] = "expired"
        item["display_status"] = "expired"
        os.environ["DRY_RUN"] = "false"
        for provider in ("ws", "cli", "desktop"):
            with self.subTest(provider=provider):
                os.environ["ACTIVATION_PROVIDER"] = provider
                self.assertEqual(activation_eligibility(item), (True, "ok"))
        self.assertTrue(desktop_oauth_status(item)["ready"])
        self.assertEqual(desktop_oauth_status(item)["missing"], [])

        self.assertEqual(
            activation_eligibility({**item, "token_revoked": True}),
            (False, "token_revoked"),
        )
        self.assertEqual(
            activation_eligibility({**item, "validity_status": "invalid"}),
            (False, "invalid_validity"),
        )

    def test_revoked_invalid_and_used_claims_are_not_formally_eligible(self) -> None:
        from app.inventory import import_cpa

        revoked = import_cpa(
            {
                "access_token": _jwt(
                    {
                        "account_id": "revoked-account",
                        "email": "revoked@example.com",
                        "exp": int(time.time()) + 3600,
                        "revoked": True,
                    }
                )
            }
        )
        self.assertFalse(revoked["details"][0]["activation_eligible"])
        self.assertEqual(revoked["details"][0]["activation_eligible_reason"], "token_revoked")

        invalid = import_cpa(
            {
                "access_token": _jwt(
                    {
                        "account_id": "invalid-claim-account",
                        "email": "invalid-claim@example.com",
                        "exp": int(time.time()) + 3600,
                        "status": "invalid",
                    }
                )
            }
        )
        self.assertFalse(invalid["details"][0]["activation_eligible"])
        self.assertEqual(invalid["details"][0]["activation_eligible_reason"], "invalid_validity")

        used = import_cpa(
            {
                "access_token": _jwt(
                    {
                        "account_id": "used-claim-account",
                        "email": "used-claim@example.com",
                        "exp": int(time.time()) + 3600,
                        "lifecycle_status": "used",
                    }
                )
            }
        )
        self.assertFalse(used["details"][0]["activation_eligible"])
        self.assertEqual(used["details"][0]["activation_eligible_reason"], "bad_lifecycle")


if __name__ == "__main__":
    unittest.main()
