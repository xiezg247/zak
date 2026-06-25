"""策略页方案 C：进页只 hydrate，默认不自动算；启用后才巡检。"""

from __future__ import annotations

from unittest.mock import MagicMock

import tests._bootstrap  # noqa: F401

from vnpy_ashare.config.preferences.watchlist_position import load_position_panel_enabled
from vnpy_ashare.config.preferences.watchlist_signal import load_signal_panel_enabled
from vnpy_ashare.ui.quotes.page.roles import STRATEGY_MONITOR_PAGE, WATCHLIST_PAGE
from vnpy_ashare.ui.quotes.page.session_lifecycle import _strategy_stale_sweep_enabled
from vnpy_ashare.ui.quotes.watchlist_signals.controller import WatchlistSignalController


def test_strategy_monitor_signal_enabled_defaults_false() -> None:
    assert load_signal_panel_enabled(page_name=STRATEGY_MONITOR_PAGE) is False


def test_strategy_monitor_position_enabled_defaults_false() -> None:
    assert load_position_panel_enabled(page_name=STRATEGY_MONITOR_PAGE) is False


def test_strategy_stale_sweep_off_when_panels_disabled() -> None:
    page = MagicMock()
    page.page_name = STRATEGY_MONITOR_PAGE
    page.signal_panel.enabled = False
    page.position_panel.enabled = False
    assert _strategy_stale_sweep_enabled(page) is False


def test_strategy_complete_stock_list_loaded_skips_auto_refresh() -> None:
    page = MagicMock()
    page.page_name = STRATEGY_MONITOR_PAGE
    page._active = True
    ctrl = WatchlistSignalController(page)
    ctrl._sync_panel_with_pool = MagicMock(return_value=["600000.SSE"])
    ctrl.hydrate_from_disk = MagicMock(return_value=True)
    ctrl._apply_refresh_result = MagicMock()
    ctrl.refresh = MagicMock()

    ctrl._complete_stock_list_loaded()

    ctrl.refresh.assert_not_called()
    ctrl._apply_refresh_result.assert_called_once()
