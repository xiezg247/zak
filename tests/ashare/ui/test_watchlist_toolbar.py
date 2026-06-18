"""自选页工具栏 policy 单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ui.quotes.features.watchlist.toolbar_policy import (
    WatchlistToolbarPolicy,
    configure_watchlist_action_button_visibility,
    watchlist_toolbar_policy,
)


class WatchlistToolbarPolicyTests(unittest.TestCase):
    def test_policy_none_without_feature(self) -> None:
        page = MagicMock()
        page._watchlist_feature = None
        self.assertIsNone(watchlist_toolbar_policy(page))

    def test_policy_present_with_feature(self) -> None:
        page = MagicMock()
        page._watchlist_feature = object()
        self.assertIsInstance(watchlist_toolbar_policy(page), WatchlistToolbarPolicy)

    def test_configure_hides_move_and_backtest_on_feature_page(self) -> None:
        page = MagicMock()
        page.config.show_watchlist_move_buttons = True
        page.config.show_backtest_button = True
        policy = WatchlistToolbarPolicy()

        show_move, show_backtest = configure_watchlist_action_button_visibility(page, policy)

        self.assertFalse(show_move)
        self.assertFalse(show_backtest)
        page.move_watchlist_up_button.setVisible.assert_called_once_with(False)
        page.move_watchlist_down_button.setVisible.assert_called_once_with(False)
        page.backtest_button.setVisible.assert_called_once_with(False)

    def test_configure_respects_config_without_feature(self) -> None:
        page = MagicMock()
        page.config.show_watchlist_move_buttons = True
        page.config.show_backtest_button = False

        show_move, show_backtest = configure_watchlist_action_button_visibility(page, None)

        self.assertTrue(show_move)
        self.assertFalse(show_backtest)


if __name__ == "__main__":
    unittest.main()
