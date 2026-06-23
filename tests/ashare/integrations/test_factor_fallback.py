"""factor_fallback 单元测试。"""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from vnpy_ashare.integrations.tushare.factor_fallback import (
    fetch_daily_basic_with_fallback,
    resolve_latest_factor_trade_date,
)


class FactorFallbackTests(unittest.TestCase):
    def test_resolve_latest_factor_trade_date_from_fallback(self) -> None:
        with patch(
            "vnpy_ashare.integrations.tushare.factor_fallback.fetch_daily_basic_with_fallback",
            return_value=([{"ts_code": "600000.SH"}], "20250620"),
        ):
            self.assertEqual(resolve_latest_factor_trade_date(), "20250620")

    def test_resolve_latest_factor_trade_date_uses_calendar_when_empty(self) -> None:
        with (
            patch(
                "vnpy_ashare.integrations.tushare.factor_fallback.fetch_daily_basic_with_fallback",
                return_value=([], ""),
            ),
            patch(
                "vnpy_ashare.integrations.tushare.factor_fallback.last_trading_day",
                return_value=date(2025, 6, 23),
            ),
        ):
            self.assertEqual(resolve_latest_factor_trade_date(), "20250623")

    def test_fetch_daily_basic_with_fallback_stops_at_first_hit(self) -> None:
        with (
            patch(
                "vnpy_ashare.integrations.tushare.factor_fallback.iter_trade_date_strs",
                return_value=["20250622", "20250620"],
            ),
            patch(
                "vnpy_ashare.integrations.tushare.factor_fallback.fetch_daily_basic",
                side_effect=[
                    ([], "20250622"),
                    ([{"ts_code": "600000.SH"}], "20250620"),
                ],
            ) as fetch,
        ):
            rows, trade_date = fetch_daily_basic_with_fallback(max_lookback=3)
        self.assertEqual(trade_date, "20250620")
        self.assertEqual(len(rows), 1)
        self.assertEqual(fetch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
