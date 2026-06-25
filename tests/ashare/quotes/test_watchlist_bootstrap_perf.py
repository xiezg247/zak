"""自选页 Bootstrap tab_resume 性能路径测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

from vnpy.trader.constant import Exchange

import tests._bootstrap  # noqa: F401
from vnpy_ashare.data import bar_store
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.ui.quotes.page.roles import STRATEGY_MONITOR_PAGE
from vnpy_ashare.ui.quotes.watchlist.bootstrap import WatchlistBootstrapCoordinator


def test_tab_resume_render_only_skips_stock_list_loaded(monkeypatch) -> None:
    coord = WatchlistBootstrapCoordinator()
    page = MagicMock()
    page.page_name = STRATEGY_MONITOR_PAGE
    page._active = True
    page.config.show_watchlist_signals = True
    page.config.show_watchlist_positions = True
    page.config.show_watchlist_multiview = False

    page._signals.cache_covers_panel.return_value = True
    page._positions.cache_covers_panel.return_value = True

    coord._run_downstream(page, reason="tab_resume")

    page._signals.render_on_resume.assert_called_once()
    page._positions.render_on_resume.assert_called_once()
    page._signals.on_stock_list_loaded.assert_not_called()
    page._positions.on_stock_list_loaded.assert_not_called()


def test_on_pool_ready_strategy_skips_apply_filter() -> None:
    coord = WatchlistBootstrapCoordinator()
    page = MagicMock()
    page.page_name = STRATEGY_MONITOR_PAGE
    page._active = True
    page._watchlist_groups = None
    page._strategy_monitor_feature = MagicMock()
    item = StockItem(symbol="600000", exchange=Exchange.SSE, name="浦发银行")
    pool = [item]

    coord.on_pool_ready(page, pool, source="pool_ready")

    page.apply_filter.assert_not_called()
    assert page.all_stocks == pool
    assert page.display_stocks == pool
    page._strategy_monitor_feature.on_stock_list_loaded.assert_called_once()


def test_cold_start_hydrate_covers_panel_skips_stock_list_loaded() -> None:
    coord = WatchlistBootstrapCoordinator()
    page = MagicMock()
    page.page_name = STRATEGY_MONITOR_PAGE
    page._active = True
    page.config.show_watchlist_signals = True
    page.config.show_watchlist_positions = True
    page.config.show_watchlist_multiview = False

    page._signals.hydrate_from_disk.return_value = True
    page._positions.hydrate_from_disk.return_value = True
    page._signals.cache_covers_panel.return_value = True
    page._positions.cache_covers_panel.return_value = True

    coord._run_downstream(page, reason="pool_ready")

    page._signals.hydrate_from_disk.assert_called_once()
    page._positions.hydrate_from_disk.assert_called_once()
    page._signals.render_on_resume.assert_called_once()
    page._positions.render_on_resume.assert_called_once()
    page._signals.on_stock_list_loaded.assert_not_called()
    page._positions.on_stock_list_loaded.assert_not_called()


def test_on_activate_cold_start_loads_pool_without_stock_list() -> None:
    coord = WatchlistBootstrapCoordinator()
    page = MagicMock()
    page.page_name = "自选"
    page._active = True
    page.display_stocks = []
    page._watchlist_groups = None
    coord._last_pool_fingerprint = None
    item = StockItem(symbol="600000", exchange=Exchange.SSE, name="浦发银行")
    pool = [item]
    page._watchlist._pool_from_service.return_value = pool

    coord.on_activate(page)

    page.load_stock_list.assert_not_called()
    page._watchlist._pool_from_service.assert_called_once()
    page.apply_filter.assert_called_once()
    assert page.watchlist_pool_stocks == pool


def test_on_activate_tab_resume_skips_load_stock_list() -> None:
    coord = WatchlistBootstrapCoordinator()
    page = MagicMock()
    page.page_name = "自选"
    page._active = True
    item = StockItem(symbol="600000", exchange=Exchange.SSE, name="浦发银行")
    pool = [item]
    page.display_stocks = pool
    coord._last_pool_fingerprint = coord.pool_fingerprint(pool)
    page._watchlist._pool_from_service.return_value = pool

    coord.on_activate(page)

    page.load_stock_list.assert_not_called()


def test_is_overview_cache_warmed_false_before_warm() -> None:
    bar_store.invalidate_bar_overview_cache()
    assert bar_store.is_overview_cache_warmed() is False
