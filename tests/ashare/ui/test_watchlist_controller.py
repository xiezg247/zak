"""engine_access 与 WatchlistController 测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy.trader.constant import Exchange

import tests._bootstrap  # noqa: F401
from vnpy_ashare.app.engine_access import (
    get_ashare_engine,
    get_service,
    get_watchlist_service,
)
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.ui.quotes.controllers.watchlist import WatchlistController


class EngineAccessTests(unittest.TestCase):
    def test_get_ashare_engine_none(self) -> None:
        self.assertIsNone(get_ashare_engine(None))

    def test_get_watchlist_service(self) -> None:
        watchlist_service = MagicMock()
        ashare_engine = MagicMock()
        ashare_engine.watchlist_service = watchlist_service
        with patch(
            "vnpy_ashare.app.engine_access.get_ashare_engine",
            return_value=ashare_engine,
        ):
            result = get_watchlist_service(MagicMock())
        self.assertIs(result, watchlist_service)

    def test_get_service_returns_watchlist(self) -> None:
        watchlist_service = MagicMock()
        ashare_engine = MagicMock()
        ashare_engine.watchlist_service = watchlist_service
        with patch(
            "vnpy_ashare.app.engine_access.get_ashare_engine",
            return_value=ashare_engine,
        ):
            result = get_service(MagicMock(), "watchlist_service")
        self.assertIs(result, watchlist_service)


class WatchlistControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.page = MagicMock()
        self.page.all_stocks = []
        self.page.config.show_add_watchlist_button = True
        self.page.config.show_remove_watchlist_button = True
        self.page.config.show_watchlist_move_buttons = True
        self.page.add_watchlist_button = MagicMock()
        self.page.remove_watchlist_button = MagicMock()
        self.page.move_watchlist_up_button = MagicMock()
        self.page.move_watchlist_down_button = MagicMock()
        self.page.status_label = MagicMock()
        self.page.status_label.setText = MagicMock()
        self.service = MagicMock()
        self.service.get_items.return_value = [
            {"symbol": "600519", "exchange": "SSE", "name": "贵州茅台"},
        ]
        self.page._get_watchlist_service.return_value = self.service
        self.controller = WatchlistController(self.page)

    def test_refresh_keys_from_service(self) -> None:
        self.controller.refresh_keys()
        self.assertIn(("600519", Exchange.SSE), self.controller.keys)

    def test_contains_on_watchlist_page_without_keys_cache(self) -> None:
        self.page.page_name = "自选"
        item = StockItem(symbol="000001", exchange=Exchange.SZSE, name="平安银行")
        self.assertTrue(self.controller.contains(item))

    def test_add_selected_delegates_to_service(self) -> None:
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="贵州茅台")
        self.page.current_item = item
        self.page.quote_map = {}
        self.service.add.return_value = True
        self.page._update_action_buttons = MagicMock()

        self.controller.add_selected()

        self.service.add.assert_called_once_with("600519", Exchange.SSE, "贵州茅台")
        self.page.status_label.setText.assert_called()


if __name__ == "__main__":
    unittest.main()
