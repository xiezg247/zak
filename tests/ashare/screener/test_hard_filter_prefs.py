"""选股硬过滤偏好测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.screener.hard_filter_prefs import (
    HardFilterPrefs,
    default_hard_filter_prefs,
    load_hard_filter_prefs,
    save_hard_filter_prefs,
)
from vnpy_ashare.screener.hard_filters import (
    recipe_exclude_st_enabled,
    recipe_min_amount_yuan,
    recipe_min_total_mv_wan,
)


class HardFilterPrefsTests(unittest.TestCase):
    def tearDown(self) -> None:
        save_hard_filter_prefs(default_hard_filter_prefs())

    def test_save_and_load_roundtrip(self) -> None:
        prefs = HardFilterPrefs(exclude_st=False, min_amount_wan=5000.0, min_total_mv_yi=80.0)
        save_hard_filter_prefs(prefs)
        loaded = load_hard_filter_prefs()
        self.assertFalse(loaded.exclude_st)
        self.assertEqual(loaded.min_amount_wan, 5000.0)
        self.assertEqual(loaded.min_total_mv_yi, 80.0)

    def test_hard_filters_read_from_prefs(self) -> None:
        save_hard_filter_prefs(HardFilterPrefs(exclude_st=True, min_amount_wan=2000.0, min_total_mv_yi=30.0))
        self.assertEqual(recipe_min_amount_yuan(), 20_000_000.0)
        self.assertEqual(recipe_min_total_mv_wan(), 300_000.0)
        self.assertTrue(recipe_exclude_st_enabled())


if __name__ == "__main__":
    unittest.main()
