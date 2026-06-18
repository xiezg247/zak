"""隔日退出分 K 评估测试。"""

from __future__ import annotations

import unittest
from datetime import datetime

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData

from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.domain.trading.position import PositionRecord
from vnpy_ashare.trading.exit.overnight_exit_intraday import evaluate_overnight_exit_intraday


def _bar(hour: int, minute: int, *, high: float, close: float, open_price: float = 9.8) -> BarData:
    return BarData(
        symbol="600001",
        exchange=Exchange.SSE,
        datetime=datetime(2026, 6, 18, hour, minute, tzinfo=CHINA_TZ),
        interval=Interval.MINUTE,
        open_price=open_price,
        high_price=high,
        low_price=close - 0.05,
        close_price=close,
        volume=1000.0,
        gateway_name="TEST",
    )


class OvernightExitIntradayTest(unittest.TestCase):
    def _record(self) -> PositionRecord:
        return PositionRecord(
            symbol="600001",
            exchange="SSE",
            name="",
            cost_price=10.0,
            volume=100,
            buy_date="2026-06-17",
        )

    def test_opening_stop_triggers_sell(self) -> None:
        bars = [_bar(9, 40, high=9.9, close=9.85)]
        snapshot = evaluate_overnight_exit_intraday(
            bars,
            self._record(),
            prev_close=10.0,
            phase="partial",
        )
        self.assertEqual(snapshot.signal, "sell")
        self.assertTrue(any(rule.rule_id == "opening_30min_stop" for rule in snapshot.rules))

    def test_stop_loss_pct(self) -> None:
        bars = [_bar(14, 30, high=9.2, close=9.0, open_price=9.1)]
        snapshot = evaluate_overnight_exit_intraday(
            bars,
            self._record(),
            prev_close=10.0,
            stop_loss_pct=0.05,
            phase="closed",
        )
        self.assertEqual(snapshot.signal, "sell")
        self.assertTrue(any(rule.rule_id == "stop_loss_pct" for rule in snapshot.rules))


if __name__ == "__main__":
    unittest.main()
