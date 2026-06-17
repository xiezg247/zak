"""已实现盈亏同步与 float_loss_hold 测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy_ashare.domain.trading.position import PositionSnapshot
from vnpy_ashare.storage.connection import init_app_db
from vnpy_ashare.storage.repositories import trade_journal as journal_repo
from vnpy_ashare.trading.journal.float_loss_hold import (
    is_float_loss_hold,
    record_float_loss_hold_if_needed,
)
from vnpy_ashare.trading.journal.prompt import build_journal_prompt
from vnpy_ashare.trading.risk.realized_pnl import resolve_realized_pnl_today


def _snap(**kwargs) -> PositionSnapshot:
    defaults = dict(
        vt_symbol="600000.SSE",
        name="测试",
        cost_price=10.0,
        volume=100,
        buy_date="2026-06-10",
        source="manual",
        last_price=9.0,
        market_value=900.0,
        unrealized_pnl=-100.0,
        unrealized_pnl_pct=-10.0,
        exit_signal="hold",
        signal_snapshot=None,
        t1_locked=False,
        exit_ref_price=None,
        dist_exit_pct=None,
        warnings=(),
    )
    defaults.update(kwargs)
    return PositionSnapshot(**defaults)  # type: ignore[arg-type]


class RealizedPnlSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch("vnpy_ashare.storage.connection._db_path", return_value=self.db_path)
        self._patcher.start()
        init_app_db()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_resolve_realized_from_journal(self) -> None:
        journal_repo.insert_trade_journal_entry(
            symbol="600519",
            exchange="SSE",
            side="sell",
            trade_date="2026-06-17",
            price=110.0,
            volume=100,
            pnl=1000.0,
        )
        with (
            patch(
                "vnpy_ashare.trading.risk.realized_pnl.today_trade_date",
                return_value="2026-06-17",
            ),
            patch(
                "vnpy_ashare.trading.risk.realized_pnl.load_trading_risk_prefs",
            ) as mock_prefs,
        ):
            from vnpy_ashare.config.preferences.trading_risk import TradingRiskPrefs

            mock_prefs.return_value = TradingRiskPrefs(
                total_capital=100_000.0,
                per_trade_risk_pct=0.02,
                stop_loss_pct=0.05,
                daily_pnl_pct=None,
                realized_pnl_today=200.0,
                caution_daily_pct=-3.0,
                halt_daily_pct=-5.0,
                caution_float_pct=-5.0,
                manual_halt=False,
            )
            effective, journal, manual = resolve_realized_pnl_today("2026-06-17")
        self.assertAlmostEqual(journal, 1000.0)
        self.assertAlmostEqual(manual or 0, 200.0)
        self.assertAlmostEqual(effective or 0, 1200.0)

    def test_float_loss_hold_journal_once(self) -> None:
        snap = _snap()
        with patch(
            "vnpy_ashare.trading.journal.float_loss_hold.today_trade_date",
            return_value="2026-06-17",
        ):
            first = record_float_loss_hold_if_needed(snap, trade_date="2026-06-17")
            second = record_float_loss_hold_if_needed(snap, trade_date="2026-06-17")
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        entries = journal_repo.query_trade_journal(start_date="2026-06-17", end_date="2026-06-17")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].side, "hold")
        self.assertIn("float_loss_hold", entries[0].violation_tags)

    def test_is_float_loss_hold_false_after_sell(self) -> None:
        journal_repo.insert_trade_journal_entry(
            symbol="600000",
            exchange="SSE",
            side="sell",
            trade_date="2026-06-15",
            price=9.5,
            volume=100,
            pnl=-50.0,
        )
        self.assertFalse(is_float_loss_hold(_snap()))

    def test_build_journal_prompt_contains_sections(self) -> None:
        with patch(
            "vnpy_ashare.trading.journal.prompt.load_emotion_cycle_snapshot",
            return_value=None,
        ):
            payload = build_journal_prompt(days=1)
        prompt = str(payload.get("prompt") or "")
        self.assertIn("流水统计", prompt)


if __name__ == "__main__":
    unittest.main()
