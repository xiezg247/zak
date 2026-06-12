"""market_overview_loaders 单元测试。"""

from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from vnpy_ashare.quotes.market_breadth import compute_market_breadth, merge_official_limit_counts
from vnpy_ashare.quotes.market_overview_loaders import load_sector_ranks


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
        with patch(
            "vnpy_ashare.screener.sector.sector_summary.fetch_stock_industry_map",
            return_value=mapping,
        ):
            sectors = load_sector_ranks(rows, top_n=2)
        self.assertEqual(len(sectors), 2)
        self.assertEqual(sectors[0].industry, "银行")
        self.assertEqual(sectors[0].avg_change_pct, 3.0)

    def test_merge_official_limit_counts(self) -> None:
        base = compute_market_breadth([{"change_pct": 10.0, "amount": 0}])
        self.assertEqual(base.limit_source, "approx")

        with patch(
            "vnpy_ashare.integrations.tushare.factors.fetch_limit_list_d",
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
        base = replace(compute_market_breadth([{"change_pct": 1.0, "amount": 0}]), limit_up=9, limit_down=1)
        with patch(
            "vnpy_ashare.integrations.tushare.factors.fetch_limit_list_d",
            return_value=([], "20250612"),
        ):
            merged = merge_official_limit_counts(base)
        self.assertEqual(merged.limit_up, 9)
        self.assertEqual(merged.limit_source, "approx")


if __name__ == "__main__":
    unittest.main()
