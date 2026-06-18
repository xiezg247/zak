"""周期回撤熔断测试。"""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from vnpy_ashare.config.preferences.trading_risk import TradingRiskPrefs
from vnpy_ashare.domain.trading.position import PositionSnapshot
from vnpy_ashare.trading.risk.drawdown import (
    DEFAULT_HALT_TOTAL_DRAWDOWN_PCT,
    compute_current_equity,
    evaluate_drawdown,
    reset_peak_equity,
)
from vnpy_ashare.trading.risk.gate import build_risk_gate_snapshot


def _prefs(**kwargs) -> TradingRiskPrefs:
    base = TradingRiskPrefs(
        total_capital=100_000.0,
        per_trade_risk_pct=0.02,
        stop_loss_pct=0.05,
        daily_pnl_pct=None,
        realized_pnl_today=None,
        caution_daily_pct=-3.0,
        halt_daily_pct=-5.0,
        caution_float_pct=-5.0,
        manual_halt=False,
        peak_equity=100_000.0,
        week_peak_equity=100_000.0,
        week_peak_key="2026-W25",
        halt_until=None,
        halt_reason="",
    )
    return base.model_copy(update=kwargs)


def _snap(vt_symbol: str, *, pnl: float) -> PositionSnapshot:
    return PositionSnapshot(
        vt_symbol=vt_symbol,
        name="测试",
        cost_price=10.0,
        volume=100,
        buy_date="2026-06-17",
        source="manual",
        last_price=10.0,
        market_value=1000.0,
        unrealized_pnl=pnl,
        unrealized_pnl_pct=-5.0,
        exit_signal="hold",
        signal_snapshot=None,
        t1_locked=False,
        exit_ref_price=None,
        dist_exit_pct=None,
        warnings=(),
    )


class DrawdownRiskGateTest(unittest.TestCase):
    def test_compute_current_equity(self) -> None:
        cache = {"600519.SSE": _snap("600519.SSE", pnl=-3000.0)}
        with patch("vnpy_ashare.trading.risk.drawdown.sum_realized_pnl_all", return_value=-2000.0):
            equity = compute_current_equity(total_capital=100_000.0, position_cache=cache)
        self.assertEqual(equity, 95_000.0)

    def test_total_drawdown_triggers_halt(self) -> None:
        prefs = _prefs(peak_equity=100_000.0)
        cache = {"600519.SSE": _snap("600519.SSE", pnl=-11_000.0)}
        with (
            patch("vnpy_ashare.trading.risk.drawdown.sum_realized_pnl_all", return_value=0.0),
            patch("vnpy_ashare.trading.risk.drawdown.save_trading_risk_prefs") as save_mock,
            patch("vnpy_ashare.trading.risk.drawdown._today", return_value=date(2026, 6, 18)),
        ):
            updated, weekly_dd, total_dd, warnings = evaluate_drawdown(
                prefs,
                position_cache=cache,
                persist=True,
            )
        self.assertIsNotNone(total_dd)
        assert total_dd is not None
        self.assertLessEqual(total_dd, DEFAULT_HALT_TOTAL_DRAWDOWN_PCT)
        self.assertEqual(updated.halt_reason, "total_drawdown")
        self.assertIsNotNone(updated.halt_until)
        self.assertTrue(any("熔断" in item for item in warnings))
        save_mock.assert_called()

    def test_build_risk_gate_snapshot_halt_on_timed_drawdown(self) -> None:
        prefs = _prefs(
            halt_until="2026-06-20",
            halt_reason="weekly_drawdown",
            peak_equity=100_000.0,
            week_peak_equity=100_000.0,
        )
        with (
            patch("vnpy_ashare.trading.risk.gate.load_trading_risk_prefs", return_value=prefs),
            patch("vnpy_ashare.trading.risk.gate.evaluate_drawdown", return_value=(prefs, -6.0, -3.0, ["单周回撤熔断中，停手至 2026-06-20"])),
        ):
            snap = build_risk_gate_snapshot()
        self.assertEqual(snap.state, "halt")
        self.assertFalse(snap.allow_new_positions)
        self.assertEqual(snap.halt_until, "2026-06-20")

    def test_reset_peak_equity(self) -> None:
        with patch("vnpy_ashare.trading.risk.drawdown.save_trading_risk_prefs") as save_mock:
            reset_peak_equity(total_capital=120_000.0)
        saved = save_mock.call_args[0][0]
        self.assertEqual(saved.peak_equity, 120_000.0)
        self.assertIsNone(saved.halt_until)


if __name__ == "__main__":
    unittest.main()
