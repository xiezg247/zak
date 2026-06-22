"""交易流水维护测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy_ashare.storage.connection import init_app_db
from vnpy_ashare.storage.repositories import trade_journal as journal_repo
from vnpy_ashare.trading.journal.maintain import delete_journal_entry, update_journal_entry


class TradeJournalMaintainTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch("vnpy_ashare.storage.connection._db_path", return_value=self.db_path)
        self._patcher.start()
        init_app_db()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_query_trade_journal_side_filter(self) -> None:
        journal_repo.insert_trade_journal_entry(
            symbol="600519",
            exchange="SSE",
            side="buy",
            trade_date="2026-06-20",
            price=100.0,
            volume=100,
        )
        journal_repo.insert_trade_journal_entry(
            symbol="600519",
            exchange="SSE",
            side="sell",
            trade_date="2026-06-20",
            price=110.0,
            volume=100,
            pnl=1000.0,
        )
        sells = journal_repo.query_trade_journal(
            start_date="2026-06-20",
            end_date="2026-06-20",
            side="sell",
        )
        self.assertEqual(len(sells), 1)
        self.assertEqual(sells[0].side, "sell")

    def test_update_sell_recalculates_pnl(self) -> None:
        journal_repo.insert_trade_journal_entry(
            symbol="600519",
            exchange="SSE",
            side="buy",
            trade_date="2026-06-19",
            price=100.0,
            volume=100,
        )
        entry_id = journal_repo.insert_trade_journal_entry(
            symbol="600519",
            exchange="SSE",
            side="sell",
            trade_date="2026-06-20",
            price=110.0,
            volume=100,
            pnl=1000.0,
            pnl_pct=10.0,
        )
        self.assertIsNotNone(entry_id)
        updated = update_journal_entry(int(entry_id), price=105.0)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertAlmostEqual(updated.pnl or 0, 500.0)
        self.assertAlmostEqual(updated.pnl_pct or 0, 5.0)

    def test_delete_journal_entry(self) -> None:
        entry_id = journal_repo.insert_trade_journal_entry(
            symbol="600000",
            exchange="SSE",
            side="sell",
            trade_date="2026-06-20",
            price=10.0,
            volume=100,
            pnl=-50.0,
        )
        self.assertIsNotNone(entry_id)
        self.assertTrue(delete_journal_entry(int(entry_id)))
        self.assertIsNone(journal_repo.get_trade_journal_entry(int(entry_id)))


if __name__ == "__main__":
    unittest.main()
