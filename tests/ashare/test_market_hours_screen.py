"""盘中选股时刻计算测试。"""

from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from vnpy_ashare.domain.time.market_hours import next_intraday_screen_at, screen_after_collect_delay_seconds


class TestMarketHoursScreen(unittest.TestCase):
    def test_screen_after_collect_delay_default(self) -> None:
        self.assertGreaterEqual(screen_after_collect_delay_seconds(), 30)

    def test_next_intraday_screen_after_collect_delay(self) -> None:
        tz = ZoneInfo("Asia/Shanghai")
        now = datetime(2026, 6, 10, 10, 0, 0, tzinfo=tz)
        nxt = next_intraday_screen_at(now, collect_interval_seconds=30)
        delay = screen_after_collect_delay_seconds()
        self.assertGreaterEqual(nxt, now)
        self.assertGreaterEqual((nxt - now).total_seconds(), 30 + delay - 5)


if __name__ == "__main__":
    unittest.main()
