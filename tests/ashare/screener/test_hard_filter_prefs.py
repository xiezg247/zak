"""选股硬过滤偏好测试。"""

from __future__ import annotations

import os
import unittest

from vnpy_ashare.screener.hard_filter_prefs import (
    HardFilterPrefs,
    default_hard_filter_prefs,
    load_hard_filter_prefs,
    save_hard_filter_prefs,
)
from vnpy_ashare.screener.hard_filters import (
    recipe_allowed_industries,
    recipe_exclude_st_enabled,
    recipe_min_amount_yuan,
    recipe_min_total_mv_wan,
)


class HardFilterPrefsTests(unittest.TestCase):
    def setUp(self) -> None:
        from vnpy_common.storage.config import force_database_url, reset_storage_config

        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            self.skipTest("需要 DATABASE_URL")
        reset_storage_config()
        force_database_url(url)

    def tearDown(self) -> None:
        from vnpy_common.storage.config import reset_storage_config

        save_hard_filter_prefs(default_hard_filter_prefs())
        reset_storage_config()

    def test_save_and_load_roundtrip(self) -> None:
        prefs = HardFilterPrefs(
            exclude_st=False,
            exclude_suspended=True,
            min_amount_wan=5000.0,
            min_total_mv_yi=80.0,
            exclude_new_listing=False,
            min_listing_days=60,
            exclude_limit_board=False,
            allowed_industries="",
            allowed_market_boards="",
        )
        save_hard_filter_prefs(prefs)
        loaded = load_hard_filter_prefs()
        self.assertFalse(loaded.exclude_st)
        self.assertTrue(loaded.exclude_suspended)
        self.assertEqual(loaded.min_amount_wan, 5000.0)
        self.assertEqual(loaded.min_total_mv_yi, 80.0)

    def test_hard_filters_read_from_prefs(self) -> None:
        save_hard_filter_prefs(
            HardFilterPrefs(
                exclude_st=True,
                exclude_suspended=True,
                min_amount_wan=2000.0,
                min_total_mv_yi=30.0,
                exclude_new_listing=False,
                min_listing_days=60,
                exclude_limit_board=False,
                allowed_industries="",
                allowed_market_boards="",
            )
        )
        self.assertEqual(recipe_min_amount_yuan(), 20_000_000.0)
        self.assertEqual(recipe_min_total_mv_wan(), 300_000.0)
        self.assertTrue(recipe_exclude_st_enabled())

    def test_allowed_industries_roundtrip(self) -> None:
        save_hard_filter_prefs(
            HardFilterPrefs(
                exclude_st=True,
                exclude_suspended=True,
                min_amount_wan=0.0,
                min_total_mv_yi=0.0,
                exclude_new_listing=False,
                min_listing_days=60,
                exclude_limit_board=False,
                allowed_industries="银行,白酒",
                allowed_market_boards="沪深主板",
            )
        )
        loaded = load_hard_filter_prefs()
        self.assertEqual(loaded.allowed_industries, "银行,白酒")
        self.assertEqual(loaded.allowed_market_boards, "沪深主板")
        self.assertEqual(recipe_allowed_industries(), frozenset({"银行", "白酒"}))
        from vnpy_ashare.screener.hard_filters import recipe_allowed_market_boards

        self.assertEqual(recipe_allowed_market_boards(), frozenset({"沪深主板"}))


if __name__ == "__main__":
    unittest.main()
