"""策略信号区：仅手动刷新触发 Worker；进页/加名单只 hydrate。"""

from __future__ import annotations

from unittest.mock import MagicMock

import tests._bootstrap  # noqa: F401
from vnpy_ashare.config.preferences.watchlist_position import load_position_panel_enabled
from vnpy_ashare.config.preferences.watchlist_signal import (
    SIGNAL_LOOKBACK_BARS,
    load_signal_panel_enabled,
)
from vnpy_ashare.ui.quotes.page.roles import STRATEGY_MONITOR_PAGE
from vnpy_ashare.ui.quotes.page.session_lifecycle import _strategy_stale_sweep_enabled
from vnpy_ashare.ui.quotes.watchlist_signals.controller import WatchlistSignalController


def test_signal_lookback_bars_is_sixty() -> None:
    assert SIGNAL_LOOKBACK_BARS == 60


def test_strategy_monitor_signal_enabled_defaults_false() -> None:
    assert load_signal_panel_enabled(page_name=STRATEGY_MONITOR_PAGE) is False


def test_strategy_monitor_position_enabled_defaults_false() -> None:
    assert load_position_panel_enabled(page_name=STRATEGY_MONITOR_PAGE) is False


def test_strategy_stale_sweep_off_when_position_disabled() -> None:
    page = MagicMock()
    page.page_name = STRATEGY_MONITOR_PAGE
    page.position_panel.enabled = False
    assert _strategy_stale_sweep_enabled(page) is False


def test_strategy_stale_sweep_on_when_position_enabled() -> None:
    page = MagicMock()
    page.page_name = STRATEGY_MONITOR_PAGE
    page.position_panel.enabled = True
    assert _strategy_stale_sweep_enabled(page) is True


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


def test_on_symbols_changed_does_not_submit_worker() -> None:
    page = MagicMock()
    page.page_name = STRATEGY_MONITOR_PAGE
    page.signal_panel.symbols = ["600000.SSE", "600519.SSE"]
    page.signal_panel.render_panel = MagicMock()
    page.watchlist_pool_items.return_value = []
    page.signal_cache = {}
    page.continuation_cache = {}

    ctrl = WatchlistSignalController(page)
    ctrl._canonicalize_symbols = MagicMock(side_effect=lambda xs: xs)
    ctrl._rekey_signal_cache = MagicMock()
    ctrl.refresh = MagicMock()

    ctrl.on_symbols_changed()

    ctrl.refresh.assert_not_called()
    page.signal_panel.render_panel.assert_called_once()


def test_should_submit_worker_only_when_force() -> None:
    page = MagicMock()
    ctrl = WatchlistSignalController(page)
    assert ctrl._should_submit_worker(force=False) is False
    assert ctrl._should_submit_worker(force=True) is True
