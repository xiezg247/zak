"""持仓异动判定测试。"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.position_snapshot import PositionSnapshot
from vnpy_ashare.quotes.position_anomaly import (
    format_anomaly_tags,
    is_position_anomaly,
    position_anomaly_reasons,
    position_anomaly_score,
)
from vnpy_ashare.quotes.snapshot import QuoteSnapshot


def _snap(
    *,
    exit_signal: str = "hold",
    unrealized_pnl_pct: float | None = None,
) -> PositionSnapshot:
    return PositionSnapshot(
        vt_symbol="600000.SSE",
        name="测试",
        cost_price=10.0,
        volume=100,
        buy_date="2026-06-10",
        source="manual",
        last_price=10.0,
        market_value=1000.0,
        unrealized_pnl=0.0,
        unrealized_pnl_pct=unrealized_pnl_pct,
        exit_signal=exit_signal,  # type: ignore[arg-type]
        signal_snapshot=None,
        t1_locked=False,
        exit_ref_price=None,
        dist_exit_pct=None,
        warnings=(),
    )


def _quote(*, change_pct: float = 0.0, volume_ratio: float = 0.0, last_price: float = 10.0) -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol="600000.SH",
        name="测试",
        last_price=last_price,
        prev_close=10.0,
        open_price=10.0,
        high_price=10.0,
        low_price=10.0,
        change_amount=change_pct,
        change_pct=change_pct,
        turnover_rate=1.0,
        volume=1000.0,
        volume_ratio=volume_ratio,
    )


class PositionAnomalyTests(unittest.TestCase):
    def test_no_anomaly_when_empty(self) -> None:
        self.assertFalse(is_position_anomaly(snap=None, quote=None))
        self.assertEqual(position_anomaly_reasons(snap=None, quote=None), ())

    def test_sell_signal_is_anomaly(self) -> None:
        reasons = position_anomaly_reasons(snap=_snap(exit_signal="sell"), quote=None)
        self.assertIn("卖出信号", reasons)
        self.assertTrue(is_position_anomaly(snap=_snap(exit_signal="sell"), quote=None))

    def test_intraday_drop(self) -> None:
        reasons = position_anomaly_reasons(snap=None, quote=_quote(change_pct=-3.5))
        self.assertIn("急跌", reasons)

    def test_volume_spike_with_move(self) -> None:
        reasons = position_anomaly_reasons(snap=None, quote=_quote(change_pct=-2.0, volume_ratio=1.5))
        self.assertIn("放量", reasons)

    def test_float_loss(self) -> None:
        reasons = position_anomaly_reasons(snap=_snap(unrealized_pnl_pct=-6.0), quote=None)
        self.assertIn("浮亏", reasons)

    def test_float_gain(self) -> None:
        reasons = position_anomaly_reasons(snap=_snap(unrealized_pnl_pct=16.0), quote=None)
        self.assertIn("浮盈", reasons)

    def test_anomaly_score_orders_by_severity(self) -> None:
        sell_only = position_anomaly_score(("卖出信号",))
        drop_only = position_anomaly_score(("急跌",))
        self.assertGreater(sell_only, drop_only)

    def test_format_anomaly_tags(self) -> None:
        text = format_anomaly_tags(("卖出信号", "浮亏"))
        self.assertEqual(text, "卖出信号 · 浮亏")


if __name__ == "__main__":
    unittest.main()
