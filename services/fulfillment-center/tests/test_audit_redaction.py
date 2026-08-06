from __future__ import annotations

import json
import os
import tempfile
import unittest


class AuditRedactionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["DATABASE_PATH"] = os.path.join(self.tmp.name, "audit.sqlite3")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_sensitive_fields_and_embedded_tokens_are_redacted(self) -> None:
        from app.audit import list_audit, write_audit

        write_audit(
            "test.redaction",
            payload={
                "password": "password-secret",
                "access_token": "access-secret",
                "nested": {"refresh_token": "refresh-secret"},
                "error": "Bearer bearer-secret access_token=url-secret",
            },
        )
        payload = list_audit(1)[0]["payload"]
        self.assertNotIn("password-secret", payload)
        self.assertNotIn("access-secret", payload)
        self.assertNotIn("refresh-secret", payload)
        self.assertNotIn("bearer-secret", payload)
        self.assertNotIn("url-secret", payload)
        self.assertIn("[REDACTED]", payload)
        self.assertEqual(json.loads(payload)["password"], "[REDACTED]")


if __name__ == "__main__":
    unittest.main()
