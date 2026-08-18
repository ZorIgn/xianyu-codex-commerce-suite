from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch


class InventoryFormatsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.previous_database_path = os.environ.get("DATABASE_PATH")
        os.environ["DATABASE_PATH"] = os.path.join(self.tmp.name, "inventory.sqlite3")
        os.environ["DRY_RUN"] = "true"

    def tearDown(self) -> None:
        if self.previous_database_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = self.previous_database_path
        self.tmp.cleanup()

    def test_parser_recognizes_wrappers_camel_case_and_filters_sub2api_apikey(self) -> None:
        from app.inventory_formats import parse_account_payload

        parsed = parse_account_payload(
            {
                "type": "sub2api-data",
                "version": 1,
                "accounts": [
                    {
                        "name": "oauth@example.com",
                        "platform": "openai",
                        "type": "oauth",
                        "credentials": {"accessToken": "access", "refreshToken": "refresh"},
                    },
                    {
                        "name": "key@example.com",
                        "platform": "openai",
                        "type": "apikey",
                        "credentials": {"apiKey": "do-not-import"},
                    },
                ],
            }
        )
        self.assertEqual(len(parsed.accounts), 1)
        self.assertEqual(parsed.accounts[0]["credentials"]["access_token"], "access")
        self.assertEqual(parsed.skipped, 1)
        self.assertEqual(parsed.detected_formats, ("sub2api",))

        auth = parse_account_payload(
            {"authMode": "oauth", "tokens": {"accessToken": "access", "refreshToken": "refresh"}}
        )
        self.assertEqual(auth.accounts[0]["tokens"]["refresh_token"], "refresh")

    def test_three_export_formats_parse_back(self) -> None:
        from app.inventory_formats import build_inventory_export, parse_account_payload

        rows = [
            {
                "id": 1,
                "email": "one@example.com",
                "account_id": "account-one",
                "primary_token": "access-one",
                "refresh_token": "refresh-one",
                "id_token": "id-one",
                "updated_at": "2026-08-01T00:00:00Z",
            },
            {
                "id": 2,
                "email": "two@example.com",
                "account_id": "account-two",
                "primary_token": "access-two",
                "refresh_token": "refresh-two",
                "id_token": "id-two",
                "updated_at": "2026-08-01T00:00:00Z",
            },
        ]
        cockpit = build_inventory_export(rows, "cockpit_tools")
        sub2api = build_inventory_export(rows, "sub2api")
        cpa = build_inventory_export(rows, "cpa")
        self.assertIsInstance(cockpit, list)
        self.assertEqual(len(parse_account_payload(cockpit).accounts), 2)
        self.assertEqual(len(parse_account_payload(sub2api).accounts), 2)
        self.assertIsInstance(cpa, list)
        self.assertEqual(len(parse_account_payload(cpa).accounts), 2)
        self.assertEqual(sub2api["accounts"][0]["type"], "oauth")
        self.assertEqual(sub2api["accounts"][0]["concurrency"], 3)
        self.assertEqual(sub2api["accounts"][0]["priority"], 50)

    def test_parser_supports_account_maps_and_raw_access_token_lines(self) -> None:
        import base64

        from app.inventory_formats import parse_account_payload

        payload = base64.urlsafe_b64encode(
            json.dumps({"email": "token@example.com"}).encode("utf-8")
        ).decode("ascii").rstrip("=")
        token = f"header.{payload}.signature"
        parsed = parse_account_payload(
            {
                "first": {"email": "one@example.com", "access_token": "one"},
                "second": {"email": "two@example.com", "access_token": "two"},
            }
        )
        self.assertEqual(len(parsed.accounts), 2)
        token_parsed = parse_account_payload(token)
        self.assertEqual(token_parsed.accounts[0]["access_token"], token)

    def test_bulk_delete_keeps_blocked_and_failed_ids_isolated(self) -> None:
        from app.inventory import InventoryDeleteBlocked, bulk_delete_inventory_items

        with patch(
            "app.inventory.delete_inventory_item",
            side_effect=[InventoryDeleteBlocked("busy"), None, KeyError("missing"), RuntimeError("db")],
        ) as delete:
            result = bulk_delete_inventory_items([1, 2, 3, 4])
        self.assertEqual(delete.call_count, 4)
        self.assertEqual(result["requested"], 4)
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(result["blocked"], 1)
        self.assertEqual(result["not_found"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertNotIn("busy", json.dumps(result))

    def test_bulk_delete_deduplicates_inventory_ids(self) -> None:
        from app.inventory import bulk_delete_inventory_items

        with patch("app.inventory.delete_inventory_item", return_value={}) as delete:
            result = bulk_delete_inventory_items([7, 7, 8])
        self.assertEqual(delete.call_count, 2)
        self.assertEqual(result["requested"], 2)
        self.assertEqual(result["deleted"], 2)

    def test_credentials_are_absent_from_list_and_audit(self) -> None:
        from app.audit import list_audit
        from app.inventory import import_cpa, list_inventory

        secret = "access-secret-value"
        import_cpa(
            {
                "email": "private@example.com",
                "account_id": "private-account",
                "access_token": secret,
                "refresh_token": "refresh-secret-value",
            }
        )
        listed = json.dumps(list_inventory(), ensure_ascii=False)
        audited = json.dumps(list_audit(), ensure_ascii=False)
        self.assertNotIn(secret, listed)
        self.assertNotIn("refresh-secret-value", listed)
        self.assertNotIn(secret, audited)
        self.assertNotIn("refresh-secret-value", audited)
        self.assertIn("credential_fields_present", listed)


if __name__ == "__main__":
    unittest.main()
