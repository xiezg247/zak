"""交易计划与流水测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.connection import init_app_db
from vnpy_ashare.storage.repositories import trade_journal as journal_repo
from vnpy_ashare.storage.repositories import trading_plans as plans_repo
from vnpy_ashare.storage.repositories import watchlist as watchlist_repo
from vnpy_ashare.trading.journal.plan_check import check_buy_against_plan
from vnpy_ashare.trading.journal.record_buy import record_buy_from_position


class TradingPlanJournalTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch("vnpy_ashare.storage.connection._db_path", return_value=self.db_path)
        self._patcher.start()
        self._emotion_patcher = patch(
            "vnpy_ashare.trading.journal.plan_check.load_emotion_cycle_snapshot",
            return_value=None,
        )
        self._emotion_patcher.start()
        init_app_db()

    def tearDown(self) -> None:
        self._emotion_patcher.stop()
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_off_plan_when_not_in_active_plan(self) -> None:
        plan_id = plans_repo.create_trading_plan(
            trade_date="2026-06-17",
            max_position_pct=0.5,
            status="draft",
        )
        assert plan_id
        plans_repo.replace_trading_plan_symbols(plan_id, [("600519", Exchange.SSE)])
        plans_repo.activate_trading_plan(plan_id)

        check = check_buy_against_plan("600000", Exchange.SSE, trade_date="2026-06-17")
        self.assertFalse(check.on_plan)
        self.assertIn("off_plan", check.violation_tags)

        check_ok = check_buy_against_plan("600519", Exchange.SSE, trade_date="2026-06-17")
        self.assertTrue(check_ok.on_plan)
        self.assertNotIn("off_plan", check_ok.violation_tags)

    def test_record_buy_writes_journal(self) -> None:
        watchlist_repo.add_watchlist_item("600000", Exchange.SSE, "浦发银行")
        plan_id = plans_repo.create_trading_plan(trade_date="2026-06-17", status="draft")
        assert plan_id
        plans_repo.activate_trading_plan(plan_id)

        entry_id = record_buy_from_position(
            "600000",
            Exchange.SSE,
            cost_price=10.0,
            volume=100,
            buy_date="2026-06-17",
        )
        self.assertIsNotNone(entry_id)
        entries = journal_repo.query_trade_journal(start_date="2026-06-17", end_date="2026-06-17")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].side, "buy")
        self.assertIn("off_plan", entries[0].violation_tags)

    def test_journal_summary(self) -> None:
        journal_repo.insert_trade_journal_entry(
            symbol="600519",
            exchange="SSE",
            side="buy",
            trade_date="2026-06-17",
            price=100.0,
            volume=100,
            on_plan=True,
        )
        journal_repo.insert_trade_journal_entry(
            symbol="600000",
            exchange="SSE",
            side="buy",
            trade_date="2026-06-17",
            price=10.0,
            volume=100,
            on_plan=False,
            violation_tags=("off_plan",),
        )
        summary = journal_repo.summarize_trade_journal(
            start_date="2026-06-17",
            end_date="2026-06-17",
        )
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["off_plan_count"], 1)


if __name__ == "__main__":
    unittest.main()
