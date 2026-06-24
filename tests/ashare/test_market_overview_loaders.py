"""market_overview_loaders 单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.domain.market.environment import MarketEnvironmentSnapshot
from vnpy_ashare.domain.market.overview import MarketOverviewData
from vnpy_ashare.quotes.market.market_breadth import MarketBreadthSnapshot, compute_market_breadth, merge_official_limit_counts
from vnpy_ashare.quotes.market.market_overview_loaders import (
    build_overview_from_market_rows,
    is_market_overview_stale,
    load_market_overview,
    load_sector_ranks,
)


class MarketOverviewLoaderTests(unittest.TestCase):
    def test_load_sector_ranks(self) -> None:
        rows = [
            {"vt_symbol": "600000.SSE", "change_pct": 2.0},
            {"vt_symbol": "600016.SSE", "change_pct": 4.0},
            {"vt_symbol": "601398.SSE", "change_pct": 3.0},
            {"vt_symbol": "000001.SZSE", "change_pct": 1.0},
            {"vt_symbol": "000002.SZSE", "change_pct": 3.0},
            {"vt_symbol": "000858.SZSE", "change_pct": 2.0},
        ]
        mapping = {
            "600000.SH": "银行",
            "600016.SH": "银行",
            "601398.SH": "银行",
            "000001.SZ": "白酒",
            "000002.SZ": "白酒",
            "000858.SZ": "白酒",
        }
        l2_to_l1 = {"银行": "金融", "白酒": "食品饮料"}
        with (
            patch(
                "vnpy_ashare.screener.sector.sector_summary.fetch_stock_industry_map",
                return_value=mapping,
            ),
            patch(
                "vnpy_ashare.quotes.market.market_overview_loaders.fetch_industry_l2_to_l1_map",
                return_value=l2_to_l1,
            ),
        ):
            sectors = load_sector_ranks(rows, top_n=2)
        self.assertEqual(len(sectors), 2)
        self.assertEqual(sectors[0].industry, "银行")
        self.assertEqual(sectors[0].industry_l1, "金融")
        self.assertEqual(sectors[0].avg_change_pct, 3.0)

    def test_merge_official_limit_counts(self) -> None:
        base = compute_market_breadth([{"change_pct": 10.0, "amount": 0}])
        self.assertEqual(base.limit_source, "approx")

        with patch(
            "vnpy_ashare.quotes.market.market_breadth.fetch_limit_list_d",
            return_value=(
                [{"limit": "U"}, {"limit": "U"}, {"limit": "D"}],
                "20250612",
            ),
        ):
            merged = merge_official_limit_counts(base)
        self.assertEqual(merged.limit_up, 2)
        self.assertEqual(merged.limit_down, 1)
        self.assertEqual(merged.limit_source, "tushare")

    def test_merge_official_limit_counts_keeps_base_when_empty(self) -> None:
        base = compute_market_breadth([{"change_pct": 1.0, "amount": 0}]).model_copy(update={"limit_up": 9, "limit_down": 1})
        with patch(
            "vnpy_ashare.quotes.market.market_breadth.fetch_limit_list_d",
            return_value=([], "20250612"),
        ):
            merged = merge_official_limit_counts(base)
        self.assertEqual(merged.limit_up, 9)
        self.assertEqual(merged.limit_source, "approx")

    def test_is_market_overview_stale_by_north_date(self) -> None:
        data = MarketOverviewData(
            indices=[],
            breadth=None,
            sectors=[],
            environment=MarketEnvironmentSnapshot(
                fear_greed_index=48.0,
                fear_greed_label="中性",
                north_money=100.0,
                north_trade_date="20250620",
            ),
        )
        with patch(
            "vnpy_ashare.quotes.market.market_overview_loaders.resolve_latest_factor_trade_date",
            return_value="20250623",
        ):
            self.assertTrue(is_market_overview_stale(data))

    def test_is_market_overview_stale_when_off_session_has_intraday_timestamp(self) -> None:
        data = MarketOverviewData(
            indices=[],
            breadth=MarketBreadthSnapshot(
                up=1,
                down=1,
                flat=0,
                limit_up=0,
                limit_down=0,
                total_amount=1.0,
                sample_size=2,
                updated_at="2025-06-23T14:39:00",
            ),
            sectors=[],
            environment=None,
        )
        with patch(
            "vnpy_ashare.quotes.market.market_overview_loaders.is_ashare_trading_session",
            return_value=False,
        ):
            self.assertTrue(is_market_overview_stale(data))

    def test_load_market_overview_force_skips_off_session_peek(self) -> None:
        cached = MarketOverviewData(
            indices=[],
            breadth=MarketBreadthSnapshot(
                up=1,
                down=1,
                flat=0,
                limit_up=0,
                limit_down=0,
                total_amount=1.0,
                sample_size=2,
            ),
            sectors=[],
            environment=MarketEnvironmentSnapshot(
                fear_greed_index=40.0,
                fear_greed_label="恐惧",
                north_money=10.0,
                north_trade_date="20250620",
            ),
        )
        fresh_env = MarketEnvironmentSnapshot(
            fear_greed_index=50.0,
            fear_greed_label="中性",
            north_money=20.0,
            north_trade_date="20250623",
        )
        with (
            patch(
                "vnpy_ashare.quotes.market.market_overview_loaders.peek_market_overview_data",
                return_value=cached,
            ) as peek,
            patch(
                "vnpy_ashare.quotes.market.market_overview_loaders.load_quote_rows_for_market",
                return_value=([], None),
            ),
            patch(
                "vnpy_ashare.quotes.market.market_overview_loaders._fetch_sorted_indices",
                return_value=[],
            ),
            patch(
                "vnpy_ashare.quotes.market.market_overview_loaders.load_market_environment",
                return_value=fresh_env,
            ),
            patch(
                "vnpy_ashare.quotes.market.market_overview_loaders._load_breadth",
                return_value=None,
            ) as load_breadth,
            patch("vnpy_ashare.quotes.market.market_overview_loaders.store_market_overview_data"),
        ):
            result = load_market_overview(intraday=False, force=True)
        peek.assert_not_called()
        load_breadth.assert_called_once()
        self.assertEqual(result.environment, fresh_env)

    def test_build_overview_from_market_rows_off_session_computes_sectors(self) -> None:
        rows = [
            {"vt_symbol": "600000.SSE", "change_pct": 2.0},
            {"vt_symbol": "600016.SSE", "change_pct": 4.0},
            {"vt_symbol": "601398.SSE", "change_pct": 3.0},
            {"vt_symbol": "000001.SZSE", "change_pct": 1.0},
            {"vt_symbol": "000002.SZSE", "change_pct": 3.0},
            {"vt_symbol": "000858.SZSE", "change_pct": 2.0},
        ]
        mapping = {
            "600000.SH": "银行",
            "600016.SH": "银行",
            "601398.SH": "银行",
            "000001.SZ": "白酒",
            "000002.SZ": "白酒",
            "000858.SZ": "白酒",
        }
        with (
            patch(
                "vnpy_ashare.quotes.market.market_overview_loaders.is_ashare_trading_session",
                return_value=False,
            ),
            patch(
                "vnpy_ashare.screener.sector.sector_summary.fetch_stock_industry_map",
                return_value=mapping,
            ),
            patch(
                "vnpy_ashare.quotes.market.market_overview_loaders.fetch_industry_l2_to_l1_map",
                return_value={"银行": "金融", "白酒": "食品饮料"},
            ),
            patch(
                "vnpy_ashare.quotes.market.market_overview_loaders.peek_market_overview_data",
                return_value=None,
            ),
        ):
            breadth, sectors = build_overview_from_market_rows(rows, updated_at="20250623")
        self.assertIsNotNone(breadth)
        self.assertEqual(len(sectors), 2)
        self.assertEqual(sectors[0].industry, "银行")


if __name__ == "__main__":
    unittest.main()
