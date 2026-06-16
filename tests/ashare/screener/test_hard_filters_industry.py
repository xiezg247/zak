"""选股硬过滤：限定行业与市场板块。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.screener.hard_filter_prefs import (
    HardFilterPrefs,
    default_hard_filter_prefs,
    normalize_allowed_industries_text,
    normalize_allowed_market_boards_text,
    parse_allowed_industries,
    parse_allowed_market_boards,
    save_hard_filter_prefs,
)
from vnpy_ashare.screener.hard_filters import (
    apply_recipe_filters,
    clear_suspend_screening_cache,
    passes_industry_filter,
    passes_market_board_filter,
    row_industry,
)


class HardFiltersIndustryTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_suspend_screening_cache()
        save_hard_filter_prefs(default_hard_filter_prefs())

    def test_normalize_and_parse_industries(self) -> None:
        self.assertEqual(normalize_allowed_industries_text(" 银行 ， 白酒 "), "银行,白酒")
        self.assertEqual(parse_allowed_industries("银行,白酒"), frozenset({"银行", "白酒"}))

    def test_apply_recipe_filters_by_allowed_industries(self) -> None:
        save_hard_filter_prefs(
            HardFilterPrefs(
                exclude_st=False,
                exclude_suspended=False,
                min_amount_wan=0.0,
                min_total_mv_yi=0.0,
                exclude_new_listing=False,
                min_listing_days=60,
                exclude_limit_board=False,
                allowed_industries="银行",
                allowed_market_boards="",
            )
        )
        rows = [
            {"vt_symbol": "600000.SSE", "name": "浦发银行", "industry": "银行", "amount": 1},
            {"vt_symbol": "600519.SSE", "name": "贵州茅台", "industry": "白酒", "amount": 1},
        ]
        industry_map = {"600000.SH": "银行", "600519.SH": "白酒"}
        with patch("vnpy_ashare.screener.hard_filters._industry_map_for_screening", return_value=industry_map):
            filtered = apply_recipe_filters(rows)
        self.assertEqual([row["vt_symbol"] for row in filtered], ["600000.SSE"])

    def test_row_industry_falls_back_to_map(self) -> None:
        row = {"vt_symbol": "600000.SSE"}
        industry_map = {"600000.SH": "银行"}
        self.assertEqual(row_industry(row, industry_map), "银行")
        self.assertTrue(passes_industry_filter(row, frozenset({"银行"}), industry_map=industry_map))

    def test_market_board_filter(self) -> None:
        self.assertEqual(normalize_allowed_market_boards_text("沪深主板,未知"), "沪深主板")
        self.assertEqual(parse_allowed_market_boards("创业板,科创板"), frozenset({"创业板", "科创板"}))
        row_main = {"symbol": "600519", "vt_symbol": "600519.SSE", "amount": 1}
        row_gem = {"symbol": "300750", "vt_symbol": "300750.SZSE", "amount": 1}
        self.assertTrue(passes_market_board_filter(row_main, frozenset({"沪深主板"})))
        self.assertFalse(passes_market_board_filter(row_gem, frozenset({"沪深主板"})))

    def test_apply_recipe_filters_by_market_board(self) -> None:
        save_hard_filter_prefs(
            HardFilterPrefs(
                exclude_st=False,
                exclude_suspended=False,
                min_amount_wan=0.0,
                min_total_mv_yi=0.0,
                exclude_new_listing=False,
                min_listing_days=60,
                exclude_limit_board=False,
                allowed_industries="",
                allowed_market_boards="创业板",
            )
        )
        rows = [
            {"symbol": "600519", "vt_symbol": "600519.SSE", "amount": 1},
            {"symbol": "300750", "vt_symbol": "300750.SZSE", "amount": 1},
        ]
        filtered = apply_recipe_filters(rows)
        self.assertEqual([row["symbol"] for row in filtered], ["300750"])


if __name__ == "__main__":
    unittest.main()
