"""分 K 打板评估测试。"""

from __future__ import annotations

import unittest
from datetime import datetime

import tests._bootstrap  # noqa: F401
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval

from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.trading.signals.limit_board_intraday import evaluate_limit_board_intraday


def _bar(
    hour: int,
    minute: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> BarData:
    return BarData(
        symbol="600001",
        exchange=Exchange.SSE,
        datetime=datetime(2026, 6, 18, hour, minute, tzinfo=CHINA_TZ),
        interval=Interval.MINUTE,
        open_price=open_price,
        high_price=high,
        low_price=low,
        close_price=close,
        volume=1000,
        gateway_name="TEST",
    )


class LimitBoardIntradayTest(unittest.TestCase):
    def test_eligible_when_touch_before_cutoff(self) -> None:
        bars = [
            _bar(9, 31, open_price=10.0, high=10.5, low=10.0, close=10.4),
            _bar(9, 45, open_price=10.4, high=11.0, low=10.3, close=11.0),
        ]
        snapshot = evaluate_limit_board_intraday(
            bars,
            prev_close=10.0,
            symbol="600001",
            phase="closed",
        )
        self.assertTrue(snapshot.eligible)
        self.assertEqual(snapshot.entry_price, 11.0)
        self.assertTrue(snapshot.first_time.startswith("0945"))

    def test_reject_one_word(self) -> None:
        bars = [
            _bar(9, 31, open_price=11.0, high=11.0, low=11.0, close=11.0),
        ]
        snapshot = evaluate_limit_board_intraday(
            bars,
            prev_close=10.0,
            symbol="600001",
            reject_one_word=True,
            phase="closed",
        )
        self.assertFalse(snapshot.eligible)
        self.assertTrue(snapshot.one_word)

    def test_reject_late_touch(self) -> None:
        bars = [
            _bar(10, 31, open_price=10.5, high=11.0, low=10.4, close=11.0),
        ]
        snapshot = evaluate_limit_board_intraday(
            bars,
            prev_close=10.0,
            symbol="600001",
            cutoff_minutes=630,
            phase="closed",
        )
        self.assertFalse(snapshot.eligible)

    def test_reject_broken_board(self) -> None:
        bars = [
            _bar(9, 35, open_price=10.2, high=11.0, low=10.1, close=11.0),
            _bar(9, 40, open_price=11.0, high=11.0, low=10.5, close=10.6),
            _bar(15, 0, open_price=10.6, high=10.7, low=10.4, close=10.5),
        ]
        snapshot = evaluate_limit_board_intraday(
            bars,
            prev_close=10.0,
            symbol="600001",
            reject_broken=True,
            phase="closed",
        )
        self.assertFalse(snapshot.eligible)
        self.assertEqual(snapshot.seal_reopen_kind, "broken")


if __name__ == "__main__":
    unittest.main()
