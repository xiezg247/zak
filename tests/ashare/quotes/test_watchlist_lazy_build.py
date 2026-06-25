"""自选页 lazy build 协调器测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401

from vnpy_ashare.ui.quotes.features.watchlist.lazy_build import WatchlistLazyBuildCoordinator


def test_lazy_coordinator_skips_repeat_ensure() -> None:
    coord = WatchlistLazyBuildCoordinator()
    page = MagicMock()
    page.config.show_watchlist_signals = True
    page.config.show_watchlist_positions = True
    page.config.show_chart_tabs = False
    page.config.show_depth_panel = False
    page.config.show_stock_notes = False
    page._center_splitter = MagicMock()
    page._center_splitter_bound = True
    page.signal_panel = MagicMock()
    page.position_panel = MagicMock()

    with patch.object(coord, "ensure_strategy_panels", wraps=coord.ensure_strategy_panels) as spy:
        coord.ensure_strategy_panels(page)
        coord.ensure_strategy_panels(page)
        assert spy.call_count == 2
    assert coord.strategy_panels_ready

    coord2 = WatchlistLazyBuildCoordinator()
    page2 = MagicMock()
    page2.config.show_watchlist_signals = False
    page2.config.show_watchlist_positions = False
    page2._center_splitter = None
    coord2.ensure_strategy_panels(page2)
    assert coord2.strategy_panels_ready
