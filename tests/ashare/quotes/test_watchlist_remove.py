"""自选移出逻辑测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

import tests._bootstrap  # noqa: F401

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.ui.quotes.controllers.watchlist import WatchlistController


def _item(symbol: str = "600000") -> StockItem:
    return StockItem(symbol=symbol, exchange=Exchange.SSE, name="测试")


def test_remove_targets_prefers_multi_selection() -> None:
    page = MagicMock()
    a, b = _item("600000"), _item("600519")
    page._table.selected_items.return_value = [a, b]
    page.current_item = a
    controller = WatchlistController(page)
    assert controller._remove_targets(None) == [a, b]


def test_remove_targets_uses_context_item_when_single_select() -> None:
    page = MagicMock()
    clicked = _item("600519")
    page._table.selected_items.return_value = []
    page.current_item = _item("600000")
    controller = WatchlistController(page)
    assert controller._remove_targets(clicked) == [clicked]
