"""个股笔记 repository 测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.constant import Exchange

from tests.ashare.pg_unittest import PgStorageTestCase
from vnpy_ashare.storage.repositories import stock_notes as repo


class StockNotesRepositoryTests(PgStorageTestCase):
    def test_memo_upsert_and_load(self) -> None:
        repo.upsert_memo("600519", Exchange.SSE, "茅台逻辑")
        row = repo.load_memo("600519", Exchange.SSE)
        self.assertIsNotNone(row)
        self.assertEqual(row["body"], "茅台逻辑")
        repo.upsert_memo("600519", Exchange.SSE, "更新备忘")
        row = repo.load_memo("600519", Exchange.SSE)
        self.assertEqual(row["body"], "更新备忘")

    def test_append_and_list_entries(self) -> None:
        first = repo.append_entry("600519", Exchange.SSE, "盘中观察 1")
        second = repo.append_entry("600519", Exchange.SSE, "盘中观察 2")
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        rows = repo.list_entries("600519", Exchange.SSE, limit=10)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["body"], "盘中观察 2")
        self.assertEqual(rows[1]["body"], "盘中观察 1")

    def test_append_empty_entry(self) -> None:
        self.assertIsNone(repo.append_entry("600519", Exchange.SSE, "   "))

    def test_clear_notes_for_symbol(self) -> None:
        repo.upsert_memo("600519", Exchange.SSE, "备忘")
        repo.append_entry("600519", Exchange.SSE, "流水")
        cleared = repo.clear_notes_for_symbol("600519", Exchange.SSE)
        self.assertGreaterEqual(cleared["memos"], 1)
        self.assertGreaterEqual(cleared["entries"], 1)
        self.assertIsNone(repo.load_memo("600519", Exchange.SSE))
        self.assertEqual(repo.list_entries("600519", Exchange.SSE), [])

    def test_list_note_index_rows(self) -> None:
        repo.upsert_memo("600519", Exchange.SSE, "茅台长文备忘")
        repo.append_entry("600519", Exchange.SSE, "流水 1")
        repo.append_entry("000001", Exchange.SZSE, "另一票")
        rows = repo.list_note_index_rows()
        self.assertEqual(len(rows), 2)
        row_519 = next(item for item in rows if item["symbol"] == "600519")
        self.assertTrue(row_519["has_memo"])
        self.assertEqual(int(row_519["entry_count"]), 1)
        self.assertIn("茅台", str(row_519["memo_preview"]))
        row_001 = next(item for item in rows if item["symbol"] == "000001")
        self.assertFalse(row_001["has_memo"])
        self.assertEqual(int(row_001["entry_count"]), 1)


if __name__ == "__main__":
    unittest.main()
