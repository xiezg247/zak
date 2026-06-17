"""卖出流水与复盘报表测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.position_snapshot import PositionRecord
from vnpy_ashare.storage.connection import init_app_db
from vnpy_ashare.storage.repositories import trade_journal as journal_repo
from vnpy_ashare.trading.journal.record_add import should_tag_add_loss
from vnpy_ashare.trading.journal.record_sell import record_sell_from_position
from vnpy_ashare.trading.journal.report import build_journal_report


class JournalSellReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch("vnpy_ashare.storage.connection._db_path", return_value=self.db_path)
        self._patcher.start()
        self._emotion_patcher = patch(
            "vnpy_ashare.trading.journal.record_sell.load_emotion_cycle_snapshot",
            return_value=None,
        )
        self._emotion_patcher.start()
        init_app_db()

    def tearDown(self) -> None:
        self._emotion_patcher.stop()
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_record_sell_with_pnl(self) -> None:
        journal_repo.insert_trade_journal_entry(
            symbol="600519",
            exchange="SSE",
            side="buy",
            trade_date="2026-06-17",
            price=100.0,
            volume=100,
            on_plan=True,
        )
        entry_id = record_sell_from_position(
            "600519",
            Exchange.SSE,
            cost_price=100.0,
            volume=100,
            sell_price=110.0,
            sell_date="2026-06-18",
        )
        self.assertIsNotNone(entry_id)
        entries = journal_repo.query_trade_journal(start_date="2026-06-18", end_date="2026-06-18")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].side, "sell")
        self.assertAlmostEqual(entries[0].pnl or 0, 1000.0)

    def test_journal_report_win_rate(self) -> None:
        journal_repo.insert_trade_journal_entry(
            symbol="600519",
            exchange="SSE",
            side="sell",
            trade_date="2026-06-17",
            price=110.0,
            volume=100,
            pnl=1000.0,
        )
        journal_repo.insert_trade_journal_entry(
            symbol="600000",
            exchange="SSE",
            side="sell",
            trade_date="2026-06-17",
            price=9.0,
            volume=100,
            pnl=-100.0,
        )
        entries = journal_repo.query_trade_journal(start_date="2026-06-17", end_date="2026-06-17")
        report = build_journal_report(entries)
        self.assertEqual(report.win_count, 1)
        self.assertEqual(report.loss_count, 1)
        self.assertAlmostEqual(report.win_rate_pct or 0, 50.0)
        self.assertAlmostEqual(report.profit_loss_ratio or 0, 10.0)

    def test_should_tag_add_loss(self) -> None:
        record = PositionRecord("600519", "SSE", "", 100.0, 100, "2026-06-01")
        self.assertTrue(should_tag_add_loss(record, new_volume=200, last_price=95.0))
        self.assertFalse(should_tag_add_loss(record, new_volume=200, last_price=105.0))
        self.assertFalse(should_tag_add_loss(record, new_volume=100, last_price=90.0))


if __name__ == "__main__":
    unittest.main()
