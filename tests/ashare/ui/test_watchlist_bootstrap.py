"""WatchlistBootstrapCoordinator 测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy.trader.constant import Exchange

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.ui.quotes.watchlist.bootstrap import WatchlistBootstrapCoordinator


def _item(symbol: str, *, exchange: Exchange = Exchange.SSE) -> StockItem:
    return StockItem(symbol=symbol, exchange=exchange, name=symbol)


def _mock_watchlist_page(*, display_stocks: list[StockItem] | None = None) -> MagicMock:
    page = MagicMock()
    page.page_name = "自选"
    page._active = True
    page.display_stocks = list(display_stocks or [])
    page.watchlist_pool_stocks = []
    page.config.show_watchlist_signals = True
    page.config.show_watchlist_positions = True
    page.config.show_watchlist_multiview = True
    page._watchlist_groups = None
    page._watchlist_feature = None
    page._multiview.is_multiview_active.return_value = False
    return page


class WatchlistBootstrapCoordinatorTests(unittest.TestCase):
    def test_pool_fingerprint_sort_sensitive(self) -> None:
        a = [_item("600519")]
        b = [_item("000001", exchange=Exchange.SZSE), _item("600519")]
        coord = WatchlistBootstrapCoordinator()
        self.assertNotEqual(coord.pool_fingerprint(a), coord.pool_fingerprint(b))

    def test_on_activate_skips_load_when_pool_unchanged(self) -> None:
        pool = [_item("600519")]
        page = _mock_watchlist_page(display_stocks=pool)
        page._watchlist._pool_from_service.return_value = pool

        coord = WatchlistBootstrapCoordinator()
        coord._last_pool_fingerprint = coord.pool_fingerprint(pool)
        coord.on_activate(page)

        page.load_stock_list.assert_not_called()
        page.apply_filter.assert_called()

    def test_on_activate_loads_when_fingerprint_changed(self) -> None:
        pool = [_item("600519")]
        page = _mock_watchlist_page(display_stocks=pool)
        page._watchlist._pool_from_service.return_value = [_item("000001", exchange=Exchange.SZSE)]

        coord = WatchlistBootstrapCoordinator()
        coord._last_pool_fingerprint = coord.pool_fingerprint(pool)
        coord.on_activate(page)

        page.load_stock_list.assert_called_once()

    @patch(
        "vnpy_ashare.ui.quotes.watchlist.bootstrap.load_watchlist_layout_preset",
        return_value="intraday",
    )
    def test_on_pool_ready_schedules_signals_once(self, _preset: MagicMock) -> None:
        pool = [_item("600519")]
        page = _mock_watchlist_page()
        page.load_stock_list = MagicMock()

        coord = WatchlistBootstrapCoordinator()
        coord.on_pool_ready(page, pool, source="universe_load")
        coord._run_downstream(page, reason="universe_load")

        page._signals.on_stock_list_loaded.assert_called_once()

    def test_invalidate_symbols_clears_caches(self) -> None:
        page = _mock_watchlist_page()
        page.signal_cache = {"600519.SSE": MagicMock()}
        page.position_cache = {"600519.SSE": MagicMock()}

        coord = WatchlistBootstrapCoordinator()
        coord.invalidate_symbols(page, ["600519.SSE"])

        self.assertNotIn("600519.SSE", page.signal_cache)
        self.assertNotIn("600519.SSE", page.position_cache)

    def test_schedule_downstream_coalesces_while_flush_pending(self) -> None:
        page = _mock_watchlist_page()
        coord = WatchlistBootstrapCoordinator()
        coord._downstream_flush_pending = True
        coord.schedule_downstream(page, reason="pool_mutation")
        self.assertTrue(coord._downstream_dirty)
        coord._flush_downstream(page)
        page._signals.on_stock_list_loaded.assert_called_once()


if __name__ == "__main__":
    unittest.main()
