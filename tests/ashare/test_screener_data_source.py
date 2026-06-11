"""选股数据源路由测试。"""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from vnpy.trader.utility import ZoneInfo

from vnpy_ashare.screener.data.data_source import (
    daily_basic_to_quote_rows,
    fetch_daily_basic_with_fallback,
    fetch_fundamental_screening_rows,
    iter_trade_date_strs,
    load_screening_quote_snapshot,
    resolve_result_source_tag,
)
from vnpy_ashare.screener.data.factors import merge_quotes_into_fundamentals

CHINA_TZ = ZoneInfo("Asia/Shanghai")


class DataSourceRoutingTests(unittest.TestCase):
    def test_iter_trade_date_strs(self) -> None:
        dates = list(iter_trade_date_strs(max_lookback=3, start=date(2026, 6, 8)))
        self.assertEqual(dates[0], "20260608")
        self.assertEqual(len(dates), 3)

    @patch("vnpy_ashare.screener.data.data_source.fetch_daily_basic")
    def test_fetch_daily_basic_with_fallback(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = [
            ([], "20260609"),
            ([{"symbol": "600519", "vt_symbol": "600519.SSE"}], "20260608"),
        ]
        rows, trade_date = fetch_daily_basic_with_fallback(
            max_lookback=3,
            start=date(2026, 6, 9),
        )
        self.assertEqual(trade_date, "20260608")
        self.assertEqual(len(rows), 1)
        self.assertEqual(mock_fetch.call_count, 2)

    def test_merge_quotes_into_fundamentals(self) -> None:
        fund = [
            {
                "vt_symbol": "600519.SSE",
                "close": 100.0,
                "turnover_rate": 1.0,
            }
        ]
        quotes = [
            {
                "vt_symbol": "600519.SSE",
                "last_price": 1688.0,
                "turnover_rate": 2.5,
            }
        ]
        merged = merge_quotes_into_fundamentals(fund, quotes)
        self.assertEqual(merged[0]["close"], 1688.0)
        self.assertEqual(merged[0]["turnover_rate"], 2.5)
        self.assertEqual(merged[0]["source"], "quote+tushare")

    def test_daily_basic_to_quote_rows_with_pct(self) -> None:
        rows = daily_basic_to_quote_rows(
            [
                {
                    "ts_code": "600519.SH",
                    "symbol": "600519",
                    "name": "贵州茅台",
                    "vt_symbol": "600519.SSE",
                    "close": 1688.0,
                    "turnover_rate": 0.5,
                    "volume_ratio": 1.2,
                }
            ],
            trade_date="20260608",
            pct_map={"600519.SH": 2.3},
        )
        self.assertEqual(rows[0]["change_pct"], 2.3)
        self.assertEqual(rows[0]["last_price"], 1688.0)

    @patch("vnpy_ashare.screener.data.data_source.load_market_quote_rows")
    @patch("vnpy_ashare.screener.data.data_source.is_ashare_trading_session", return_value=True)
    def test_trading_session_uses_redis(
        self,
        _session: MagicMock,
        mock_redis: MagicMock,
    ) -> None:
        from vnpy_ashare.screener.data.quotes_loader import MarketQuotesSnapshot

        mock_redis.return_value = MarketQuotesSnapshot(
            rows=[{"symbol": "000001"}],
            updated_at="06-09 10:00:00",
            total=1,
            source="quote",
        )
        snap = load_screening_quote_snapshot()
        self.assertEqual(snap.source, "quote")
        mock_redis.assert_called_once()

    @patch("vnpy_ashare.screener.data.data_source.fetch_daily_pct_map", return_value={})
    @patch("vnpy_ashare.screener.data.data_source.fetch_daily_basic_with_fallback")
    @patch("vnpy_ashare.screener.data.data_source.is_ashare_trading_session", return_value=False)
    def test_off_hours_uses_daily_basic(
        self,
        _session: MagicMock,
        mock_basic: MagicMock,
        _pct: MagicMock,
    ) -> None:
        mock_basic.return_value = (
            [{"ts_code": "600519.SH", "symbol": "600519", "vt_symbol": "600519.SSE", "close": 1.0, "turnover_rate": 1.0, "volume_ratio": 1.0, "name": ""}],
            "20260608",
        )
        snap = load_screening_quote_snapshot()
        self.assertEqual(snap.source, "tushare")
        self.assertEqual(snap.updated_at, "20260608")

    @patch("vnpy_ashare.screener.data.data_source.load_market_quote_rows")
    @patch("vnpy_ashare.screener.data.data_source.fetch_daily_basic_with_fallback")
    @patch("vnpy_ashare.screener.data.data_source.is_ashare_trading_session", return_value=True)
    def test_fundamental_trading_merges_redis(
        self,
        _session: MagicMock,
        mock_fallback: MagicMock,
        mock_redis: MagicMock,
    ) -> None:
        from vnpy_ashare.screener.data.quotes_loader import MarketQuotesSnapshot

        mock_fallback.return_value = (
            [{"vt_symbol": "600519.SSE", "pe_ttm": 10, "total_mv": 1_000_000, "symbol": "600519", "name": "", "close": 100, "trade_date": "20260608"}],
            "20260608",
        )
        mock_redis.return_value = MarketQuotesSnapshot(
            rows=[{"vt_symbol": "600519.SSE", "last_price": 1688.0, "turnover_rate": 2.0}],
            updated_at="10:00",
            total=1,
        )
        rows, trade_date, source = fetch_fundamental_screening_rows()
        self.assertEqual(trade_date, "20260608")
        self.assertEqual(source, "quote+tushare")
        self.assertEqual(rows[0]["close"], 1688.0)

    def test_resolve_result_source_tag(self) -> None:
        self.assertEqual(resolve_result_source_tag("quote+tushare"), "Redis+Tushare")
        self.assertEqual(resolve_result_source_tag("tushare"), "Tushare")


if __name__ == "__main__":
    unittest.main()
