from __future__ import annotations

import os
import tempfile
import unittest


class DeliveryPrivacyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["DATABASE_PATH"] = os.path.join(self.tmp.name, "test.sqlite3")
        os.environ["DRY_RUN"] = "true"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_delivery_text_contains_email_but_never_password(self) -> None:
        from app.inventory import render_delivery_text

        text = render_delivery_text(
            [
                {"email": "one@example.com", "password": "secret-one"},
                {
                    "email": "two@example.com",
                    "password": "secret-two",
                    "primary_token": "access-token-two",
                    "refresh_token": "refresh-token-two",
                },
            ]
        )

        self.assertIn("one@example.com", text)
        self.assertIn("two@example.com", text)
        self.assertNotIn("secret-one", text)
        self.assertNotIn("secret-two", text)
        self.assertNotIn("access-token-two", text)
        self.assertNotIn("refresh-token-two", text)
        self.assertNotIn("密码", text)
