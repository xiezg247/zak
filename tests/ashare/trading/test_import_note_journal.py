"""笔记导入 trade_journal 测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.models.stock_note import StockNoteEntry
from vnpy_ashare.storage.repositories import stock_notes as notes_repo
from vnpy_ashare.storage.repositories import trade_journal as journal_repo
from vnpy_ashare.trading.journal.import_from_note import import_stock_note_by_id, import_stock_note_entry


class ImportNoteToJournalTest(unittest.TestCase):
    def test_import_stock_note_entry_writes_hold_journal(self) -> None:
        entry = StockNoteEntry(
            id=0,
            symbol="600000",
            exchange="SSE",
            body="半路介入，计划内",
            created_at="2026-06-18T10:30:00",
        )
        journal_id = import_stock_note_entry(entry)
        self.assertIsNotNone(journal_id)
        rows = journal_repo.query_trade_journal(start_date="2026-06-18", end_date="2026-06-18")
        matched = [row for row in rows if row.id == journal_id]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0].side, "hold")
        self.assertIn("半路介入", matched[0].reason)

    def test_import_by_id(self) -> None:
        row = notes_repo.append_entry("000001", Exchange.SZSE, "测试导入流水")
        self.assertIsNotNone(row)
        journal_id = import_stock_note_by_id(int(row["id"]))
        self.assertIsNotNone(journal_id)


if __name__ == "__main__":
    unittest.main()
