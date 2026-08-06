from __future__ import annotations

import os
import tempfile
import unittest


class CpaPasteParserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.previous_database_path = os.environ.get("DATABASE_PATH")
        os.environ["DATABASE_PATH"] = os.path.join(self.tmp.name, "test.sqlite3")
        from app.db import init_db

        init_db()

    def tearDown(self) -> None:
        if self.previous_database_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = self.previous_database_path
        self.tmp.cleanup()

    def test_pasted_adjacent_objects_import_as_separate_inventory_items(self) -> None:
        from app.db import connect
        from app.inventory import import_cpa

        pasted = (
            "使用说明：以下是批量库存\n"
            '{"email":"paste-one@example.com","password":"pw1","access_token":"a1"}'
            '{"email":"paste-two@example.com","password":"pw2","access_token":"a2"}'
        )
        result = import_cpa(pasted)
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["total"], 2)
        with connect() as conn:
            emails = [
                row["email"]
                for row in conn.execute(
                    "SELECT email FROM inventory_items ORDER BY id"
                ).fetchall()
            ]
        self.assertEqual(
            emails,
            ["paste-one@example.com", "paste-two@example.com"],
        )

    def test_pasted_wrapper_and_array_are_flattened(self) -> None:
        from app.inventory import _items_from_cpa

        payload = (
            "说明\n"
            '{"accounts":[{"email":"one@example.com"},{"email":"two@example.com"}]}'
            '[{"email":"three@example.com"}]'
        )
        items = _items_from_cpa(payload)
        self.assertEqual(
            [item["email"] for item in items],
            ["one@example.com", "two@example.com", "three@example.com"],
        )


if __name__ == "__main__":
    unittest.main()