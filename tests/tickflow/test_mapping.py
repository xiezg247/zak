"""vnpy_tickflow 映射测试。"""

from __future__ import annotations

import unittest
from datetime import datetime

from vnpy.trader.constant import Exchange, Interval

import tests._bootstrap  # noqa: F401
from vnpy_tickflow.mapping import (
    CHINA_TZ,
    interval_to_period,
    parse_datetime,
    to_tf_symbol,
)


class MappingTests(unittest.TestCase):
    def test_to_tf_symbol_ashare(self) -> None:
        self.assertEqual(to_tf_symbol("600519", Exchange.SSE), "600519.SH")
        self.assertEqual(to_tf_symbol("000001", Exchange.SZSE), "000001.SZ")
        self.assertEqual(to_tf_symbol("IF2506", Exchange.CFFEX), "IF2506.CFX")

    def test_interval_to_period(self) -> None:
        self.assertEqual(interval_to_period(Interval.MINUTE), "1m")
        self.assertEqual(interval_to_period(Interval.DAILY), "1d")
        self.assertIsNone(interval_to_period(Interval.TICK))

    def test_parse_datetime_trade_time(self) -> None:
        dt = parse_datetime("2026-06-06 09:31:00", Interval.MINUTE)
        expected = datetime(2026, 6, 6, 9, 30, 0, tzinfo=CHINA_TZ)
        self.assertEqual(dt, expected)

    def test_parse_datetime_timestamp(self) -> None:
        dt = parse_datetime(1780623000000, Interval.DAILY)
        self.assertEqual(dt.tzinfo, CHINA_TZ)


if __name__ == "__main__":
    unittest.main()
