"""自选页上下文条与布局预设测试。"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ui.quotes.features.watchlist.context_bar import (
    SHORT_TERM_OBSERVATION_MAX,
    format_pool_context_summary,
)
from vnpy_ashare.ui.quotes.features.watchlist.preset_specs import PRESET_PANEL_STATE, PRESET_SPECS


class WatchlistContextBarTests(unittest.TestCase):
    def test_format_pool_context_summary(self) -> None:
        text = format_pool_context_summary(
            pool_count=38,
            observation_count=4,
            signal_count=6,
            position_count=3,
        )
        self.assertIn("自选 38/50", text)
        self.assertIn(f"观察组 4/{SHORT_TERM_OBSERVATION_MAX}", text)
        self.assertIn("信号 6/10", text)
        self.assertIn("持仓 3/20", text)


class WatchlistLayoutPresetTests(unittest.TestCase):
    def test_intraday_collapses_position_panel(self) -> None:
        signal_expanded, position_expanded = PRESET_PANEL_STATE["intraday"]
        self.assertTrue(signal_expanded)
        self.assertFalse(position_expanded)

    def test_review_expands_position_only(self) -> None:
        signal_expanded, position_expanded = PRESET_PANEL_STATE["review"]
        self.assertFalse(signal_expanded)
        self.assertTrue(position_expanded)

    def test_intraday_monitor_mode(self) -> None:
        spec = PRESET_SPECS["intraday"]
        self.assertTrue(spec.select_observation_group)
        self.assertTrue(spec.force_table_view)
        self.assertFalse(spec.show_register_toolbar)
        self.assertTrue(spec.show_add_signal_toolbar)

    def test_register_mode(self) -> None:
        spec = PRESET_SPECS["register"]
        self.assertTrue(spec.position_expanded)
        self.assertTrue(spec.show_register_toolbar)

    def test_review_hides_add_signal_toolbar(self) -> None:
        spec = PRESET_SPECS["review"]
        self.assertFalse(spec.show_add_signal_toolbar)
        self.assertTrue(spec.show_register_toolbar)


if __name__ == "__main__":
    unittest.main()
