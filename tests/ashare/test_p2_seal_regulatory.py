"""封单强度与监管异动测试。"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData

from vnpy_ashare.quotes.radar.radar_leader import compute_leader_score
from vnpy_ashare.services.stock.regulatory_deviation import assess_regulatory_deviation
from vnpy_ashare.trading.signals.seal_strength import seal_strength_score


def _bar(day: int, close: float, *, prev: float) -> BarData:
    return BarData(
        gateway_name="test",
        symbol="600000",
        exchange=Exchange.SSE,
        datetime=datetime(2025, 1, 1) + timedelta(days=day - 1),
        interval=None,
        volume=1,
        turnover=1,
        open_interest=0,
        open_price=prev,
        high_price=max(close, prev),
        low_price=min(close, prev),
        close_price=close,
    )


class SealStrengthTest(unittest.TestCase):
    def test_strth_dominates(self) -> None:
        self.assertAlmostEqual(seal_strength_score(strth=85.0), 0.85)

    def test_fd_amount_and_open_times(self) -> None:
        strong = seal_strength_score(fd_amount=30_000, open_times=0)
        weak = seal_strength_score(fd_amount=500, open_times=3)
        self.assertGreater(strong, weak)

    def test_leader_score_prefers_seal_strength(self) -> None:
        base = {
            "vt_symbol": "600000.SSE",
            "change_pct": 10.0,
            "amount": 2e8,
            "net_mf_amount": 1e7,
            "limit_times": 2,
            "symbol": "600000",
            "first_time": "093500",
        }
        weak = compute_leader_score({**base, "seal_strength_score": 0.3}, amount_rank=0.8, max_net_mf=1e7)
        strong = compute_leader_score({**base, "seal_strength_score": 0.95}, amount_rank=0.8, max_net_mf=1e7)
        self.assertGreater(strong, weak)


class RegulatoryDeviationTest(unittest.TestCase):
    def test_high_risk_on_four_limit_ups(self) -> None:
        bars: list[BarData] = []
        price = 10.0
        for day in range(1, 16):
            prev = price
            price *= 1.1
            bars.append(_bar(day, price, prev=prev))
        snapshot = assess_regulatory_deviation(bars)
        self.assertGreaterEqual(snapshot.limit_up_count_10d, 4)
        self.assertEqual(snapshot.risk_level, "high")

    def test_watch_on_three_limit_ups(self) -> None:
        bars: list[BarData] = []
        price = 10.0
        for day in range(1, 20):
            prev = price
            if day >= 17:
                price *= 1.1
            else:
                price *= 1.01
            bars.append(_bar(day, price, prev=prev))
        snapshot = assess_regulatory_deviation(bars)
        self.assertEqual(snapshot.limit_up_count_10d, 3)
        self.assertEqual(snapshot.risk_level, "watch")

    def test_30d_return_threshold(self) -> None:
        bars: list[BarData] = []
        price = 10.0
        for day in range(1, 35):
            prev = price
            price *= 1.04
            bars.append(_bar(day, price, prev=prev))
        snapshot = assess_regulatory_deviation(bars)
        self.assertIsNotNone(snapshot.return_30d_pct)
        assert snapshot.return_30d_pct is not None
        self.assertGreaterEqual(snapshot.return_30d_pct, 200.0)
        self.assertEqual(snapshot.risk_level, "high")


if __name__ == "__main__":
    unittest.main()
