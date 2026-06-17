"""账户可交易市场板块（交易 Universe）。"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from vnpy_ashare.config.constants.trading import ENV_TRADING_BOARDS
from vnpy_ashare.config.trading_universe import (
    default_market_board_label,
    effective_market_board_filter,
    get_trading_allowed_boards,
    is_market_board_combo_locked,
    market_board_combo_labels,
    market_board_label_to_filter,
    passes_trading_board,
)
from vnpy_ashare.screener.hard_filter_prefs import (
    HardFilterPrefs,
    default_hard_filter_prefs,
    save_hard_filter_prefs,
)
from vnpy_ashare.screener.hard_filters import apply_recipe_filters, recipe_allowed_market_boards


class TradingUniverseTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(ENV_TRADING_BOARDS, None)
        os.environ.pop("RECIPE_ALLOWED_MARKET_BOARDS", None)
        save_hard_filter_prefs(default_hard_filter_prefs())

    def test_get_trading_allowed_boards_empty_by_default(self) -> None:
        self.assertEqual(get_trading_allowed_boards(), frozenset())

    def test_effective_boards_use_trading_when_recipe_empty(self) -> None:
        os.environ[ENV_TRADING_BOARDS] = "沪深主板"
        resolved = effective_market_board_filter(recipe_boards=frozenset())
        self.assertTrue(resolved.active)
        self.assertEqual(resolved.boards, frozenset({"沪深主板"}))

    def test_effective_boards_intersection(self) -> None:
        os.environ[ENV_TRADING_BOARDS] = "沪深主板,创业板"
        resolved = effective_market_board_filter(recipe_boards=frozenset({"创业板", "科创板"}))
        self.assertEqual(resolved.boards, frozenset({"创业板"}))

    def test_effective_boards_recipe_only_when_trading_unset(self) -> None:
        resolved = effective_market_board_filter(recipe_boards=frozenset({"科创板"}))
        self.assertTrue(resolved.active)
        self.assertEqual(resolved.boards, frozenset({"科创板"}))

    def test_effective_boards_empty_intersection_rejects_all(self) -> None:
        os.environ[ENV_TRADING_BOARDS] = "沪深主板"
        resolved = effective_market_board_filter(recipe_boards=frozenset({"创业板"}))
        self.assertTrue(resolved.active)
        self.assertEqual(resolved.boards, frozenset())

    def test_passes_trading_board(self) -> None:
        os.environ[ENV_TRADING_BOARDS] = "沪深主板"
        self.assertTrue(passes_trading_board("600519"))
        self.assertFalse(passes_trading_board("300750"))
        os.environ.pop(ENV_TRADING_BOARDS, None)
        self.assertTrue(passes_trading_board("300750"))

    def test_apply_recipe_filters_respects_trading_ceiling(self) -> None:
        os.environ[ENV_TRADING_BOARDS] = "沪深主板"
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
        self.assertEqual(filtered, [])

    def test_apply_recipe_filters_main_board_only_with_trading_env(self) -> None:
        os.environ[ENV_TRADING_BOARDS] = "沪深主板"
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
                allowed_market_boards="",
            )
        )
        rows = [
            {"symbol": "600519", "vt_symbol": "600519.SSE", "amount": 1},
            {"symbol": "300750", "vt_symbol": "300750.SZSE", "amount": 1},
            {"symbol": "688981", "vt_symbol": "688981.SSE", "amount": 1},
        ]
        filtered = apply_recipe_filters(rows)
        self.assertEqual([row["symbol"] for row in filtered], ["600519"])

    def test_recipe_env_still_narrows_within_trading(self) -> None:
        os.environ[ENV_TRADING_BOARDS] = "沪深主板,创业板"
        os.environ["RECIPE_ALLOWED_MARKET_BOARDS"] = "创业板"
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
                allowed_market_boards="",
            )
        )
        self.assertEqual(recipe_allowed_market_boards(), frozenset({"创业板"}))
        rows = [
            {"symbol": "600519", "vt_symbol": "600519.SSE", "amount": 1},
            {"symbol": "300750", "vt_symbol": "300750.SZSE", "amount": 1},
        ]
        filtered = apply_recipe_filters(rows)
        self.assertEqual([row["symbol"] for row in filtered], ["300750"])

    def test_market_board_combo_main_board_only(self) -> None:
        os.environ[ENV_TRADING_BOARDS] = "沪深主板"
        self.assertEqual(market_board_combo_labels(), ("沪深主板",))
        self.assertEqual(default_market_board_label(), "沪深主板")
        self.assertTrue(is_market_board_combo_locked())
        self.assertEqual(market_board_label_to_filter("沪深主板"), "沪深主板")

    def test_market_board_combo_multi_allowed_defaults_main(self) -> None:
        os.environ[ENV_TRADING_BOARDS] = "沪深主板,创业板"
        self.assertEqual(
            market_board_combo_labels(),
            ("全部", "沪深主板", "创业板"),
        )
        self.assertEqual(default_market_board_label(), "沪深主板")
        self.assertFalse(is_market_board_combo_locked())

    def test_market_board_combo_unrestricted(self) -> None:
        self.assertEqual(
            market_board_combo_labels()[0],
            "全部",
        )
        self.assertEqual(default_market_board_label(), "全部")
        self.assertFalse(is_market_board_combo_locked())


if __name__ == "__main__":
    unittest.main()
