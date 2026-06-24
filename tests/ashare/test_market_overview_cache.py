"""market_overview 缓存与非交易时段加载测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.domain.market.breadth import MarketBreadthSnapshot
from vnpy_ashare.domain.market.overview import MarketOverviewData
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.quotes.market.market_overview_cache import (
    invalidate_market_overview_cache,
    peek_market_overview_data,
    store_market_overview_data,
)
from vnpy_ashare.quotes.market.market_overview_loaders import build_overview_from_market_rows, load_market_overview


def _quote(symbol: str, pct: float) -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol=symbol,
        name=symbol,
        last_price=3000.0,
        prev_close=2990.0,
        open_price=2995.0,
        high_price=3010.0,
        low_price=2988.0,
        change_amount=10.0,
        change_pct=pct,
        turnover_rate=0.0,
        volume=0.0,
        amount=0.0,
    )


class MarketOverviewCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        invalidate_market_overview_cache()

    def tearDown(self) -> None:
        invalidate_market_overview_cache()

    def test_peek_intraday_vs_off_session_ttl(self) -> None:
        data = MarketOverviewData(indices=[], breadth=None, sectors=[])
        store_market_overview_data(data)
        self.assertIsNotNone(peek_market_overview_data(intraday=True))
        self.assertIsNotNone(peek_market_overview_data(intraday=False))

    def test_load_market_overview_off_session_uses_cache_without_sector_compute(self) -> None:
        cached = MarketOverviewData(
            indices=[("上证", _quote("000001.SH", 1.0))],
            breadth=MarketBreadthSnapshot(
                up=10,
                down=5,
                flat=2,
                limit_up=1,
                limit_down=0,
                total_amount=1e9,
                sample_size=0,
                updated_at="15:00",
            ),
            sectors=[],
        )
        store_market_overview_data(cached)
        with (
            patch(
                "vnpy_ashare.quotes.market.market_overview_loaders._fetch_sorted_indices",
                return_value=[("上证", _quote("000001.SH", 1.2))],
            ),
            patch(
                "vnpy_ashare.quotes.market.market_overview_loaders.load_sector_ranks",
            ) as load_sectors,
            patch(
                "vnpy_ashare.quotes.market.market_overview_loaders.load_quote_rows_for_market",
            ) as load_rows,
        ):
            result = load_market_overview(intraday=False)
        load_sectors.assert_not_called()
        load_rows.assert_not_called()
        self.assertEqual(result.indices[0][1].change_pct, 1.2)
        self.assertEqual(result.breadth, cached.breadth)

    def test_build_overview_from_market_rows_off_session_skips_merge_and_sectors(self) -> None:
        rows = [{"change_pct": 1.0, "amount": 0, "vt_symbol": "600000.SSE"}]
        store_market_overview_data(
            MarketOverviewData(
                indices=[],
                breadth=None,
                sectors=[],
            )
        )
        with (
            patch(
                "vnpy_ashare.quotes.market.market_overview_loaders.merge_official_limit_counts",
            ) as merge_official,
            patch(
                "vnpy_ashare.quotes.market.market_overview_loaders.load_sector_ranks",
            ) as load_sectors,
        ):
            breadth, sectors = build_overview_from_market_rows(rows, intraday=False)
        merge_official.assert_not_called()
        load_sectors.assert_not_called()
        self.assertIsNotNone(breadth)
        self.assertEqual(sectors, [])


if __name__ == "__main__":
    unittest.main()
