"""A 股交易时段测试。"""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

from vnpy.trader.utility import ZoneInfo

from vnpy_ashare.market_hours import (
    DAILY_CHART_TAB,
    INTRADAY_CHART_TAB,
    default_chart_tab_index,
    is_ashare_trading_session,
    next_quotes_collect_at,
)

CHINA_TZ = ZoneInfo("Asia/Shanghai")


class MarketHoursTests(unittest.TestCase):
    def test_trading_morning(self) -> None:
        dt = datetime(2026, 6, 5, 10, 0, tzinfo=CHINA_TZ)
        self.assertTrue(is_ashare_trading_session(dt))

    def test_trading_afternoon(self) -> None:
        dt = datetime(2026, 6, 5, 14, 30, tzinfo=CHINA_TZ)
        self.assertTrue(is_ashare_trading_session(dt))

    def test_lunch_break(self) -> None:
        dt = datetime(2026, 6, 5, 12, 0, tzinfo=CHINA_TZ)
        self.assertFalse(is_ashare_trading_session(dt))

    def test_weekend(self) -> None:
        dt = datetime(2026, 6, 6, 10, 0, tzinfo=CHINA_TZ)
        self.assertFalse(is_ashare_trading_session(dt))

    def test_holiday_weekday(self) -> None:
        dt = datetime(2026, 6, 5, 10, 0, tzinfo=CHINA_TZ)
        with patch("vnpy_ashare.market_hours.is_trading_day", return_value=False):
            self.assertFalse(is_ashare_trading_session(dt))

    def test_default_tab(self) -> None:
        trading = datetime(2026, 6, 5, 10, 0, tzinfo=CHINA_TZ)
        closed = datetime(2026, 6, 5, 16, 0, tzinfo=CHINA_TZ)
        self.assertEqual(default_chart_tab_index(trading), INTRADAY_CHART_TAB)
        self.assertEqual(default_chart_tab_index(closed), DAILY_CHART_TAB)

    def test_next_collect_during_session(self) -> None:
        now = datetime(2026, 6, 5, 10, 0, tzinfo=CHINA_TZ)
        nxt = next_quotes_collect_at(now, interval_seconds=15)
        self.assertEqual(nxt, datetime(2026, 6, 5, 10, 0, 15, tzinfo=CHINA_TZ))

    def test_next_collect_lunch_break(self) -> None:
        now = datetime(2026, 6, 5, 12, 10, tzinfo=CHINA_TZ)
        nxt = next_quotes_collect_at(now, interval_seconds=15)
        self.assertEqual(nxt, datetime(2026, 6, 5, 13, 0, tzinfo=CHINA_TZ))

    def test_next_collect_after_close(self) -> None:
        now = datetime(2026, 6, 5, 16, 0, tzinfo=CHINA_TZ)
        nxt = next_quotes_collect_at(now, interval_seconds=15)
        self.assertEqual(nxt, datetime(2026, 6, 8, 9, 30, tzinfo=CHINA_TZ))


if __name__ == "__main__":
    unittest.main()
