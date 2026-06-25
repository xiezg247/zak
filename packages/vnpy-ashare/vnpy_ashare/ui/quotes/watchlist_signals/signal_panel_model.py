"""信号区表格 Model（QAbstractTableModel）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.ui.quotes.table.model import QuoteCell, QuoteTableModel

_INVALID_PARENT = QtCore.QModelIndex()
_ParentIndex = QtCore.QModelIndex | QtCore.QPersistentModelIndex


class SignalPanelTableModel(QuoteTableModel):
    """信号区行数据；每行额外绑定 vt_symbol。"""

    VtSymbolRole = QtCore.Qt.ItemDataRole.UserRole + 2

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._vt_symbols: list[str] = []

    def vt_symbol_at(self, row: int) -> str:
        if 0 <= row < len(self._vt_symbols):
            return self._vt_symbols[row]
        return ""

    def row_for_vt_symbol(self, vt_symbol: str) -> int:
        target = (vt_symbol or "").strip()
        if not target:
            return -1
        for index, vt in enumerate(self._vt_symbols):
            if vt == target:
                return index
        return -1

    def set_rows_with_symbols(self, vt_symbols: list[str], rows: list[list[QuoteCell]]) -> None:
        self.beginResetModel()
        self._vt_symbols = list(vt_symbols)
        self._rows = [list(row) for row in rows]
        self._ensure_row_widths()
        self.endResetModel()

    def clear_rows(self) -> None:
        self.set_rows_with_symbols([], [])

    def data(self, index: _ParentIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> object | None:  # noqa: N802
        if role == self.VtSymbolRole and index.isValid():
            return self.vt_symbol_at(index.row()) or None
        return super().data(index, role)
