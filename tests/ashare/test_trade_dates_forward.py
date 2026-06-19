"""未来交易日遍历测试。"""

from __future__ import annotations

import unittest
from datetime import date
from unittest import mock

from vnpy_ashare.domain.time.trade_dates import iter_forward_trade_date_strs


class ForwardTradeDatesTests(unittest.TestCase):
    def test_iter_forward_trade_date_strs_weekend_anchor(self) -> None:
        with mock.patch("vnpy_ashare.domain.time.trade_dates.last_trading_day", return_value=date(2024, 9, 6)):
            with mock.patch("vnpy_ashare.domain.time.trade_dates.is_trading_day", side_effect=lambda day: day.weekday() < 5):
                dates = iter_forward_trade_date_strs(count=3, start=date(2024, 9, 6))
        self.assertEqual(dates, ("20240909", "20240910", "20240911"))

    def test_iter_forward_trade_date_strs_requires_positive_count(self) -> None:
        with mock.patch("vnpy_ashare.domain.time.trade_dates.last_trading_day", return_value=date(2024, 9, 9)):
            with mock.patch("vnpy_ashare.domain.time.trade_dates.is_trading_day", return_value=True):
                dates = iter_forward_trade_date_strs(count=1, start=date(2024, 9, 9))
        self.assertEqual(len(dates), 1)
        self.assertEqual(dates[0], "20240910")


if __name__ == "__main__":
    unittest.main()
