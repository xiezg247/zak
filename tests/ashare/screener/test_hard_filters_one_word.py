"""硬过滤：排除一字涨停。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.screener.hard_filter_prefs import HardFilterPrefs
from vnpy_ashare.screener.hard_filters import is_one_word_limit_board, passes_screening_hard_filter


class HardFilterOneWordTests(unittest.TestCase):
    def test_detect_one_word_by_amplitude(self) -> None:
        row = {
            "symbol": "600000",
            "change_pct": 10.0,
            "prev_close": 10.0,
            "high_price": 11.0,
            "low_price": 10.99,
        }
        self.assertTrue(is_one_word_limit_board(row))

    def test_not_one_word_when_amplitude_large(self) -> None:
        row = {
            "symbol": "600000",
            "change_pct": 10.0,
            "prev_close": 10.0,
            "high_price": 11.0,
            "low_price": 10.5,
        }
        self.assertFalse(is_one_word_limit_board(row))

    def test_exclude_one_word_pref(self) -> None:
        row = {
            "symbol": "600000",
            "change_pct": 10.0,
            "prev_close": 10.0,
            "high_price": 11.0,
            "low_price": 10.99,
            "amount": 100_000_000,
        }
        prefs = HardFilterPrefs(
            exclude_st=False,
            exclude_suspended=False,
            min_amount_wan=0,
            min_total_mv_yi=0,
            exclude_new_listing=False,
            min_listing_days=0,
            exclude_limit_board=False,
            exclude_one_word=True,
        )
        with patch("vnpy_ashare.screener.hard_filters.load_hard_filter_prefs", return_value=prefs):
            with patch("vnpy_ashare.screener.hard_filters.recipe_exclude_st_enabled", return_value=False):
                with patch(
                    "vnpy_ashare.screener.hard_filters.recipe_exclude_suspended_enabled",
                    return_value=False,
                ):
                    with patch(
                        "vnpy_ashare.screener.hard_filters.recipe_exclude_new_listing_enabled",
                        return_value=False,
                    ):
                        with patch(
                            "vnpy_ashare.screener.hard_filters.recipe_exclude_limit_board_enabled",
                            return_value=False,
                        ):
                            with patch(
                                "vnpy_ashare.screener.hard_filters.recipe_exclude_one_word_enabled",
                                return_value=True,
                            ):
                                self.assertFalse(passes_screening_hard_filter(row))


if __name__ == "__main__":
    unittest.main()
