"""策略监控页按需挂载测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401

from vnpy_ashare.ui.quotes.page.roles import STRATEGY_MONITOR_PAGE
from vnpy_ashare.ui.quotes.watchlist.bootstrap import WatchlistBootstrapCoordinator


def test_bootstrap_runs_signal_position_on_strategy_monitor_page() -> None:
    coord = WatchlistBootstrapCoordinator()
    page = MagicMock()
    page.page_name = STRATEGY_MONITOR_PAGE
    page._active = True
    page.config.show_watchlist_signals = True
    page.config.show_watchlist_positions = True
    page.config.show_watchlist_multiview = False

    with patch(
        "vnpy_ashare.ui.quotes.watchlist.bootstrap.load_watchlist_layout_preset",
        return_value="intraday",
    ):
        with patch("vnpy_ashare.ui.quotes.watchlist.bootstrap.QtCore.QTimer.singleShot", side_effect=lambda _ms, fn: fn()):
            coord._run_downstream(page, reason="pool_ready")

    page._signals.on_stock_list_loaded.assert_called()
    page._positions.on_stock_list_loaded.assert_not_called()


def test_bootstrap_skips_signal_position_on_watchlist_page() -> None:
    coord = WatchlistBootstrapCoordinator()
    page = MagicMock()
    page.page_name = "自选"
    page._active = True
    page.config.show_watchlist_signals = False
    page.config.show_watchlist_positions = False
    page.config.show_watchlist_multiview = False

    with patch(
        "vnpy_ashare.ui.quotes.watchlist.bootstrap.load_watchlist_layout_preset",
        return_value="intraday",
    ):
        coord._run_downstream(page, reason="pool_ready")

    page._signals.on_stock_list_loaded.assert_not_called()
    page._positions.on_stock_list_loaded.assert_not_called()
