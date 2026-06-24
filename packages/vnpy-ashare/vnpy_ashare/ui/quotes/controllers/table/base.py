"""TableController 共享状态与表格访问。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.domain.trading.signal_snapshot import SIGNAL_COLUMN_KEYS
from vnpy_ashare.ui.quotes.page.config import STATS_DEBOUNCE_MS
from vnpy_ashare.ui.quotes.table.model import QuoteTableModel

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


class TableControllerBase:
    def __init__(self, page: QuotesPage) -> None:
        self._page = page
        self.visible_columns: list[str] = []
        self.visible_tail_columns: list[str] = []
        self._symbol_row_index: dict[str, int] | None = None
        self._stats_timer = QtCore.QTimer(page)
        self._stats_timer.setSingleShot(True)
        self._stats_timer.setInterval(STATS_DEBOUNCE_MS)
        self._stats_timer.timeout.connect(self.update_stats)

    @property
    def _p(self) -> QuotesPage:
        return self._page

    def _model(self) -> QuoteTableModel:
        return self._p.quote_table_model

    def _view(self) -> QtWidgets.QTableView:
        return self._p.market_table

    def _signal_column_keys(self) -> frozenset[str]:
        return SIGNAL_COLUMN_KEYS

    def _strip_signal_columns(self, keys: list[str]) -> list[str]:
        blocked = self._signal_column_keys()
        return [key for key in keys if key not in blocked]

    def invalidate_symbol_row_index(self) -> None:
        self._symbol_row_index = None

    def _build_symbol_row_index(self) -> dict[str, int]:
        symbol_rows: dict[str, int] = {}
        for row in range(self._model().row_count()):
            item = self.stock_at_row(row)
            if item is not None:
                symbol_rows[item.tickflow_symbol] = row
        self._symbol_row_index = symbol_rows
        return symbol_rows

    def _extend_symbol_row_index(self, start_row: int, items: list[StockItem]) -> None:
        if self._symbol_row_index is None:
            self._build_symbol_row_index()
            return
        for offset, item in enumerate(items):
            self._symbol_row_index[item.tickflow_symbol] = start_row + offset

    def stock_at_row(self, row: int) -> StockItem | None:
        page = self._p
        if row < 0:
            return None
        item = self._model().stock_at_row(row)
        if item is not None:
            return item
        if row < len(page.display_stocks):
            return page.display_stocks[row]
        return None
