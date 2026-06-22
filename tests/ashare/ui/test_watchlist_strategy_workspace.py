"""自选页策略/持仓工作区测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ui.quotes.features.watchlist.strategy_workspace import (
    apply_strategy_workspace,
    format_strategy_workspace_button_label,
    is_strategy_workspace_open,
)
from vnpy_ashare.ui.quotes.features.watchlist.strategy_workspace_prefs import load_strategy_workspace_open
from vnpy_ashare.ui.quotes.watchlist_signals.splitter import compute_center_splitter_sizes


class StrategyWorkspaceLabelTests(unittest.TestCase):
    def test_format_button_label(self) -> None:
        label = format_strategy_workspace_button_label(signal_count=6, position_count=3)
        self.assertEqual(label, "策略/持仓 · 信号 6 · 持仓 3")


class StrategyWorkspaceSplitterTests(unittest.TestCase):
    def test_hidden_panels_give_table_full_height(self) -> None:
        sizes = compute_center_splitter_sizes(
            800,
            has_signal_panel=False,
            signal_expanded=False,
            has_position_panel=False,
            position_expanded=False,
            has_run_output=False,
            run_expanded=False,
        )
        self.assertEqual(sizes["signal"], 0)
        self.assertEqual(sizes["position"], 0)
        self.assertEqual(sizes["table"], 800)


class StrategyWorkspacePrefsTests(unittest.TestCase):
    @patch("vnpy_ashare.ui.quotes.features.watchlist.strategy_workspace_prefs.get_settings")
    def test_new_user_defaults_closed(self, get_settings_mock: MagicMock) -> None:
        settings = MagicMock()
        settings.contains.return_value = False
        get_settings_mock.return_value = settings
        self.assertFalse(load_strategy_workspace_open())

    @patch("vnpy_ashare.ui.quotes.features.watchlist.strategy_workspace_prefs.get_settings")
    def test_saved_pref_wins(self, get_settings_mock: MagicMock) -> None:
        settings = MagicMock()

        def _contains(key: str) -> bool:
            return key == "quotes/watchlist/strategy_workspace_open_v1"

        settings.contains.side_effect = _contains
        settings.value.return_value = True
        get_settings_mock.return_value = settings
        self.assertTrue(load_strategy_workspace_open())


class StrategyWorkspaceApplyTests(unittest.TestCase):
    def test_apply_hides_panels_when_closed(self) -> None:
        page = MagicMock()
        page._strategy_workspace_open = True
        signal_panel = MagicMock()
        position_panel = MagicMock()
        page.signal_panel = signal_panel
        page.position_panel = position_panel
        page.config.show_watchlist_signals = True
        page.config.show_watchlist_positions = True
        page.strategy_workspace_button = MagicMock()

        with patch(
            "vnpy_ashare.ui.quotes.features.watchlist.strategy_workspace.apply_toolbar_for_preset",
        ), patch(
            "vnpy_ashare.ui.quotes.features.watchlist.strategy_workspace.apply_center_splitter_sizes",
        ), patch(
            "vnpy_ashare.ui.quotes.features.watchlist.strategy_workspace.save_strategy_workspace_open",
        ):
            apply_strategy_workspace(page, False, persist=False, apply_preset=False)

        signal_panel.setVisible.assert_called_once_with(False)
        position_panel.setVisible.assert_called_once_with(False)
        self.assertFalse(is_strategy_workspace_open(page))


if __name__ == "__main__":
    unittest.main()
