"""交易参数与仓位指标测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.domain.trading.position import PositionSnapshot
from vnpy_ashare.trading.risk.metrics import (
    compute_avg_float_pnl_pct,
    format_emotion_position_hint,
)


def _snap(vt_symbol: str, *, pnl_pct: float | None = None) -> PositionSnapshot:
    return PositionSnapshot(
        vt_symbol=vt_symbol,
        name="测试",
        cost_price=10.0,
        volume=100,
        buy_date="2026-06-17",
        source="manual",
        last_price=10.0,
        market_value=1000.0,
        unrealized_pnl=0.0,
        unrealized_pnl_pct=pnl_pct,
        exit_signal="hold",
        signal_snapshot=None,
        t1_locked=False,
        exit_ref_price=None,
        dist_exit_pct=None,
        warnings=(),
    )


class TradingRiskMetricsTest(unittest.TestCase):
    def test_avg_float_pnl_pct(self) -> None:
        cache = {
            "600519.SSE": _snap("600519.SSE", pnl_pct=-6.0),
            "000001.SZSE": _snap("000001.SZSE", pnl_pct=-4.0),
        }
        self.assertAlmostEqual(compute_avg_float_pnl_pct(cache), -5.0)

    def test_format_emotion_position_hint(self) -> None:
        self.assertEqual(format_emotion_position_hint(position_pct_min=0.3, position_pct_max=0.5), "情绪建议 30–50%")
        self.assertEqual(format_emotion_position_hint(position_pct_min=0.0, position_pct_max=0.5), "情绪建议 ≤50%")


if __name__ == "__main__":
    unittest.main()
