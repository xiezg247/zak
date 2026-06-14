"""个股分析统一入口。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.ui.features.stock_analysis.dialog import StockAnalysisDialog
from vnpy_ashare.ui.features.stock_analysis.host import StockAnalysisHost

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


def show_stock_analysis_dialog(
    *,
    item: StockItem,
    host: StockAnalysisHost,
    quote: QuoteSnapshot | None = None,
    parent: QtWidgets.QWidget | None = None,
    modality: QtCore.Qt.WindowModality = QtCore.Qt.WindowModality.WindowModal,
) -> None:
    dialog = StockAnalysisDialog(item=item, host=host, quote=quote, parent=parent)
    dialog.setWindowModality(modality)
    dialog.show()


def show_stock_analysis_vt_symbol(
    vt_symbol: str,
    host: StockAnalysisHost,
    *,
    name: str = "",
    parent: QtWidgets.QWidget | None = None,
    modality: QtCore.Qt.WindowModality = QtCore.Qt.WindowModality.WindowModal,
) -> None:
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return
    if name and not item.name:
        item = StockItem(symbol=item.symbol, exchange=item.exchange, name=name)
    quote = host.quote_for_item(item)
    show_stock_analysis_dialog(
        item=item,
        host=host,
        quote=quote,
        parent=parent,
        modality=modality,
    )


def show_stock_analysis_from_quotes_page(
    item: StockItem,
    page: QuotesPage,
    *,
    quote: QuoteSnapshot | None = None,
    row_hint: dict[str, object] | None = None,
    parent: QtWidgets.QWidget | None = None,
) -> None:
    host = StockAnalysisHost.from_quotes_page(page)
    if quote is None or (quote.last_price or 0) <= 0:
        quote = host.quote_for_item(item, row_hint=row_hint)
    show_stock_analysis_dialog(item=item, host=host, quote=quote, parent=parent or page)


def _row_vt_symbol(row: dict[str, object]) -> str:
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    if vt_symbol:
        return vt_symbol
    symbol = str(row.get("symbol") or "").strip()
    exchange = str(row.get("exchange") or "").strip()
    if symbol and exchange:
        return f"{symbol}.{exchange}"
    return ""


def wire_stock_analysis_context_menu(
    table: QtWidgets.QTableWidget,
    *,
    host: StockAnalysisHost,
    row_data_role: QtCore.Qt.ItemDataRole,
    parent: QtWidgets.QWidget | None = None,
) -> None:
    """为表格绑定「个股分析」右键菜单（选股结果等）。"""

    def _on_menu(pos: QtCore.QPoint) -> None:
        index = table.indexAt(pos)
        if not index.isValid():
            return
        check_item = table.item(index.row(), 0)
        if check_item is None:
            return
        raw = check_item.data(row_data_role)
        if not isinstance(raw, dict):
            return
        vt_symbol = _row_vt_symbol(raw)
        if not vt_symbol:
            return
        name = str(raw.get("name") or "")
        menu = QtWidgets.QMenu(table)
        action = menu.addAction("个股分析")
        chosen = menu.exec(table.viewport().mapToGlobal(pos))
        if chosen is action:
            show_stock_analysis_vt_symbol(vt_symbol, host, name=name, parent=parent or table)

    table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
    table.customContextMenuRequested.connect(_on_menu)
