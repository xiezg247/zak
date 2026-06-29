"""quote_source 单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.quotes.market.quote_source import load_quote_rows_for_market, probe_intraday_market_quotes, resolve_intraday_quote_rows


class QuoteSourceTests(unittest.TestCase):
    def test_off_session_uses_tushare_fallback(self) -> None:
        with (
            patch(
                "vnpy_ashare.quotes.market.quote_source.is_ashare_trading_session",
                return_value=False,
            ),
            patch(
                "vnpy_ashare.quotes.market.quote_source.quote_rows_from_tushare_fallback",
                return_value=([{"change_pct": 1.0}], "2025-06-23"),
            ) as fallback,
        ):
            rows, updated_at = load_quote_rows_for_market()
        fallback.assert_called_once()
        self.assertEqual(len(rows), 1)
        self.assertEqual(updated_at, "2025-06-23")

    def test_intraday_uses_redis_cache_when_available(self) -> None:
        with (
            patch(
                "vnpy_ashare.quotes.market.quote_source.is_ashare_trading_session",
                return_value=True,
            ),
            patch(
                "vnpy_ashare.quotes.core.quote_rows.peek_market_quotes_cache",
                return_value=[{"change_pct": 2.0}],
            ),
            patch(
                "vnpy_ashare.quotes.market.quote_source.load_screening_quote_snapshot",
            ) as load_snapshot,
        ):
            rows, updated_at = load_quote_rows_for_market(allow_network=False)
        load_snapshot.assert_not_called()
        self.assertEqual(len(rows), 1)
        self.assertIsNone(updated_at)

    def test_resolve_intraday_prefers_cache(self) -> None:
        with (
            patch(
                "vnpy_ashare.quotes.market.quote_source.peek_market_quote_rows",
                return_value=[{"change_pct": 1.0}, {"change_pct": 2.0}],
            ),
            patch(
                "vnpy_ashare.quotes.market.quote_source.load_intraday_market_snapshot",
            ) as load_snapshot,
        ):
            rows, updated_at, total, error = resolve_intraday_quote_rows(min_cached_rows=2)
        load_snapshot.assert_not_called()
        self.assertEqual(total, 2)
        self.assertIsNone(error)
        self.assertIsNone(updated_at)

    def test_probe_intraday_market_quotes_delegates(self) -> None:
        with patch(
            "vnpy_ashare.quotes.market.quote_source.load_intraday_market_snapshot",
        ) as load_snapshot:
            probe_intraday_market_quotes()
        load_snapshot.assert_called_once_with(enrich_factors=False)


if __name__ == "__main__":
    unittest.main()
