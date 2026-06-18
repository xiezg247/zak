"""分 K 模式参考线测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.trading.signals.mode_reference import (
    build_intraday_mode_reference_lines,
    resolve_intraday_mode_kind,
)


class ModeReferenceTest(unittest.TestCase):
    def test_resolve_mode_from_strategy(self) -> None:
        self.assertEqual(resolve_intraday_mode_kind("AshareLimitBoardStrategy"), "limit_board")
        self.assertEqual(resolve_intraday_mode_kind("AshareIntradayBreakoutMinuteStrategy"), "halfway")
        self.assertEqual(resolve_intraday_mode_kind("AsharePullbackStrategy"), "pullback")
        self.assertEqual(resolve_intraday_mode_kind("AshareDoubleMaStrategy"), "none")

    def test_limit_board_lines(self) -> None:
        quote = QuoteSnapshot(
            symbol="600000",
            name="测试",
            last_price=10.0,
            prev_close=10.0,
            open_price=10.0,
            high_price=10.5,
            low_price=9.8,
            change_amount=0.0,
            change_pct=0.0,
            turnover_rate=1.0,
            volume=1000.0,
        )
        lines = build_intraday_mode_reference_lines(
            "600000.SSE",
            quote,
            mode="limit_board",
            minute_bars=[],
        )
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].label, "涨停价")
        self.assertAlmostEqual(lines[0].price, 11.0, places=2)
        self.assertEqual(lines[1].label, "昨收")

    def test_halfway_band_lines(self) -> None:
        quote = QuoteSnapshot(
            symbol="600000",
            name="测试",
            last_price=10.5,
            prev_close=10.0,
            open_price=10.1,
            high_price=10.6,
            low_price=10.0,
            change_amount=0.5,
            change_pct=5.0,
            turnover_rate=1.0,
            volume=1000.0,
        )
        lines = build_intraday_mode_reference_lines(
            "600000.SSE",
            quote,
            mode="halfway",
            minute_bars=[],
        )
        labels = [line.label for line in lines]
        self.assertIn("半路 3%", labels)
        self.assertIn("半路 7%", labels)
        self.assertIn("突破位", labels)

    def test_pullback_dip_zone_lines(self) -> None:
        quote = QuoteSnapshot(
            symbol="600000",
            name="测试",
            last_price=9.6,
            prev_close=10.0,
            open_price=10.0,
            high_price=10.1,
            low_price=9.5,
            change_amount=-0.4,
            change_pct=-4.0,
            turnover_rate=1.0,
            volume=1000.0,
        )
        lines = build_intraday_mode_reference_lines(
            "600000.SSE",
            quote,
            mode="pullback",
            minute_bars=[],
        )
        labels = [line.label for line in lines]
        self.assertIn("低吸 −5%", labels)
        self.assertIn("低吸 −3%", labels)


if __name__ == "__main__":
    unittest.main()
