"""市场表格增量渲染测试。"""

from __future__ import annotations

import pytest
from vnpy.trader.ui import QtWidgets
from vnpy.trader.constant import Exchange
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.ui.quotes.table.model import QuoteCell, QuoteTableModel


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _stock(code: str, exchange: Exchange) -> StockItem:
    return StockItem(symbol=code, exchange=exchange, name=code)


def _can_incremental_render(model: QuoteTableModel, display_stocks: list[StockItem]) -> bool:
    if model.row_count() != len(display_stocks):
        return False
    for row, item in enumerate(display_stocks):
        row_item = model.stock_at_row(row)
        if row_item is None or row_item.tickflow_symbol != item.tickflow_symbol:
            return False
    return True


def test_can_incremental_render_when_symbols_match(qapp: QtWidgets.QApplication) -> None:
    model = QuoteTableModel()
    item_a = _stock("000001", Exchange.SZSE)
    item_b = _stock("600000", Exchange.SSE)
    model.set_headers(["代码"])
    model.set_rows(
        [
            [QuoteCell(text="000001", stock_item=item_a)],
            [QuoteCell(text="600000", stock_item=item_b)],
        ]
    )
    assert _can_incremental_render(model, [item_a, item_b]) is True


def test_cannot_incremental_render_when_order_changes(qapp: QtWidgets.QApplication) -> None:
    model = QuoteTableModel()
    item_a = _stock("000001", Exchange.SZSE)
    item_b = _stock("600000", Exchange.SSE)
    model.set_headers(["代码"])
    model.set_rows(
        [
            [QuoteCell(text="000001", stock_item=item_a)],
            [QuoteCell(text="600000", stock_item=item_b)],
        ]
    )
    assert _can_incremental_render(model, [item_b, item_a]) is False
