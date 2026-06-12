"""market_environment 单元测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.quotes.market_environment import format_north_money_hsgt


class MarketEnvironmentTests(unittest.TestCase):
    def test_format_north_money_hsgt_yi(self) -> None:
        self.assertEqual(format_north_money_hsgt(1234.0), "+12.34亿")

    def test_format_north_money_hsgt_million(self) -> None:
        self.assertEqual(format_north_money_hsgt(0.5), "+0百万")

    def test_format_north_money_none(self) -> None:
        self.assertEqual(format_north_money_hsgt(None), "—")


if __name__ == "__main__":
    unittest.main()
