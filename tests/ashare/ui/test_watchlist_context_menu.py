"""自选页主表右键菜单测试。"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

import tests._bootstrap  # noqa: F401
from vnpy.trader.constant import Exchange
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.ui.quotes.controllers.actions import ActionsController


def _menu_action_labels(menu: QtWidgets.QMenu) -> list[str]:
    labels: list[str] = []
    for action in menu.actions():
        if action.isSeparator():
            continue
        submenu = action.menu()
        if submenu is not None:
            labels.extend(_menu_action_labels(submenu))
        else:
            labels.append(action.text())
    return labels


class _PageHost(QtWidgets.QWidget):
    """供 QMenu 挂载的轻量页面宿主。"""


class WatchlistContextMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _make_page(self, **kwargs: object) -> _PageHost:
        page = _PageHost()
        page.page_name = str(kwargs.get("page_name", "自选"))
        page.config = SimpleNamespace(
            show_watchlist_signals=bool(kwargs.get("show_watchlist_signals", True)),
            show_watchlist_positions=bool(kwargs.get("show_watchlist_positions", True)),
            show_remove_watchlist_button=bool(kwargs.get("show_remove_watchlist_button", True)),
            show_refresh_quotes_button=bool(kwargs.get("show_refresh_quotes_button", True)),
            use_market_rank=bool(kwargs.get("use_market_rank", False)),
            show_stock_notes=bool(kwargs.get("show_stock_notes", False)),
            show_download_button=bool(kwargs.get("show_download_button", True)),
            show_backtest_button=bool(kwargs.get("show_backtest_button", False)),
            show_watchlist_move_buttons=bool(kwargs.get("show_watchlist_move_buttons", False)),
            show_watchlist_groups=bool(kwargs.get("show_watchlist_groups", False)),
            show_add_watchlist_button=bool(kwargs.get("show_add_watchlist_button", False)),
        )
        page._watchlist = MagicMock()
        page._watchlist.contains.return_value = bool(kwargs.get("in_watchlist", True))
        page._get_position_service = MagicMock(return_value=None)
        page.add_selection_to_signal_panel = MagicMock()
        page.register_position_for_selected = MagicMock()
        page.remove_from_watchlist = MagicMock()
        page._refresh_quotes_clicked = MagicMock()
        page.add_to_watchlist = MagicMock()
        return page

    def _controller(self, page: _PageHost) -> ActionsController:
        controller = ActionsController.__new__(ActionsController)
        controller._page = page
        return controller

    def test_watchlist_page_includes_pool_actions(self) -> None:
        page = self._make_page(show_download_button=False)
        item = StockItem(symbol="600000", exchange=Exchange.SSE, name="浦发银行")
        labels = _menu_action_labels(self._controller(page)._build_stock_context_menu(item))
        self.assertIn("加入信号区", labels)
        self.assertIn("登记持仓", labels)
        self.assertIn("移出自选", labels)
        self.assertIn("刷新行情", labels)

    def test_market_page_keeps_add_watchlist_when_not_in_pool(self) -> None:
        page = self._make_page(
            page_name="市场",
            show_watchlist_signals=False,
            show_watchlist_positions=False,
            show_remove_watchlist_button=False,
            show_refresh_quotes_button=False,
            show_download_button=False,
            show_add_watchlist_button=True,
            in_watchlist=False,
        )
        item = StockItem(symbol="600000", exchange=Exchange.SSE, name="浦发银行")
        labels = _menu_action_labels(self._controller(page)._build_stock_context_menu(item))
        self.assertIn("加入自选", labels)
        self.assertNotIn("加入信号区", labels)


if __name__ == "__main__":
    unittest.main()
