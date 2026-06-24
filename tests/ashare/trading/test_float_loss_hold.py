"""浮亏扛单判定测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.domain.trading.position import PositionSnapshot
from vnpy_ashare.trading.risk.float_loss_hold import is_float_loss_hold


def _snap(**kwargs) -> PositionSnapshot:
    defaults = dict(
        vt_symbol="600000.SSE",
        name="测试",
        cost_price=10.0,
        volume=100,
        buy_date="2026-06-17",
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


class FloatLossHoldTest(unittest.TestCase):
    def test_is_float_loss_hold_below_threshold(self) -> None:
        self.assertTrue(is_float_loss_hold(_snap(), threshold_pct=-5.0))

    def test_is_float_loss_hold_above_threshold(self) -> None:
        self.assertFalse(is_float_loss_hold(_snap(unrealized_pnl_pct=-2.0), threshold_pct=-5.0))


if __name__ == "__main__":
    unittest.main()
