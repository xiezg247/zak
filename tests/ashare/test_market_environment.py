"""market_environment 单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.quotes.market.market_environment import format_north_money_hsgt, load_market_environment


class MarketEnvironmentTests(unittest.TestCase):
    def test_format_north_money_hsgt_yi(self) -> None:
        self.assertEqual(format_north_money_hsgt(1234.0), "+12.34亿")

    def test_format_north_money_hsgt_million(self) -> None:
        self.assertEqual(format_north_money_hsgt(0.5), "+0百万")

    def test_format_north_money_none(self) -> None:
        self.assertEqual(format_north_money_hsgt(None), "—")

    def test_load_market_environment_uses_calendar_date_for_hsgt(self) -> None:
        with (
            patch(
                "vnpy_ashare.quotes.market.market_environment.resolve_latest_factor_trade_date",
                return_value="20250620",
            ),
            patch(
                "vnpy_ashare.quotes.market.market_environment.last_trading_day",
                return_value=__import__("datetime").date(2025, 6, 23),
            ),
            patch(
                "vnpy_ashare.quotes.market.market_environment.try_fetch_fear_greed_index",
                return_value=None,
            ),
            patch(
                "vnpy_ashare.quotes.market.market_environment.fetch_moneyflow_hsgt_window",
                return_value=([{"trade_date": "20250623", "north_money": 100.0}], "20250623"),
            ) as fetch_hsgt,
        ):
            env = load_market_environment(force=True)
        fetch_hsgt.assert_called_once_with(trade_date="20250623", force=True)
        self.assertEqual(env.north_trade_date, "20250623")


if __name__ == "__main__":
    unittest.main()
