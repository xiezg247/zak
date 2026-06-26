"""带 vt_symbol 绑定的面板表格 Model 基类（信号区 / 持仓区共用）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.ui.quotes.table.model import QuoteCell, QuoteTableModel

_INVALID_PARENT = QtCore.QModelIndex()
_ParentIndex = QtCore.QModelIndex | QtCore.QPersistentModelIndex


class VtSymbolPanelTableModel(QuoteTableModel):
    """每行额外绑定 vt_symbol；``set_rows_with_symbols`` 尽量增量更新。"""

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
        vt_symbols = list(vt_symbols)
        row_cells = [list(row) for row in rows]
        if len(vt_symbols) != len(row_cells):
            self._reset_rows_with_symbols(vt_symbols, row_cells)
            return

        if not vt_symbols:
            if self._vt_symbols:
                self._reset_rows_with_symbols([], [])
            return

        if vt_symbols == self._vt_symbols:
            for index, cells in enumerate(row_cells):
                self.apply_row(index, cells)
            return

        if len(vt_symbols) == len(self._vt_symbols) and set(vt_symbols) == set(self._vt_symbols):
            if vt_symbols != self._vt_symbols:
                self.reorder_symbols(vt_symbols)
            for index, cells in enumerate(row_cells):
                self.apply_row(index, cells)
            return

        self._sync_rows_with_symbols(vt_symbols, row_cells)

    def clear_rows(self) -> None:
        self.set_rows_with_symbols([], [])

    def reorder_symbols(self, vt_symbols: list[str]) -> bool:
        """仅调整行序，避免 sort 变化时整表 reset。"""
        if len(vt_symbols) != len(self._vt_symbols):
            return False
        if set(vt_symbols) != set(self._vt_symbols):
            return False
        index_by_vt = {vt: index for index, vt in enumerate(self._vt_symbols)}
        self._rows = [self._rows[index_by_vt[vt]] for vt in vt_symbols]
        self._vt_symbols = list(vt_symbols)
        self.layoutChanged.emit()
        return True

    def data(self, index: _ParentIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> object | None:  # noqa: N802
        if role == self.VtSymbolRole and index.isValid():
            return self.vt_symbol_at(index.row()) or None
        return super().data(index, role)

    def _reset_rows_with_symbols(self, vt_symbols: list[str], rows: list[list[QuoteCell]]) -> None:
        self.beginResetModel()
        self._vt_symbols = list(vt_symbols)
        self._rows = [list(row) for row in rows]
        self._ensure_row_widths()
        self.endResetModel()

    def _sync_rows_with_symbols(self, vt_symbols: list[str], rows: list[list[QuoteCell]]) -> None:
        new_set = set(vt_symbols)
        for index in range(len(self._vt_symbols) - 1, -1, -1):
            if self._vt_symbols[index] not in new_set:
                self.beginRemoveRows(_INVALID_PARENT, index, index)
                del self._vt_symbols[index]
                del self._rows[index]
                self.endRemoveRows()

        for target_idx, vt in enumerate(vt_symbols):
            cells = rows[target_idx]
            current_idx = self.row_for_vt_symbol(vt)
            if current_idx < 0:
                self.beginInsertRows(_INVALID_PARENT, target_idx, target_idx)
                self._vt_symbols.insert(target_idx, vt)
                self._rows.insert(target_idx, list(cells))
                self._ensure_row_widths()
                self.endInsertRows()
                continue
            if current_idx != target_idx:
                dest_child = target_idx + 1 if target_idx > current_idx else target_idx
                if not self.beginMoveRows(_INVALID_PARENT, current_idx, current_idx, _INVALID_PARENT, dest_child):
                    self._reset_rows_with_symbols(vt_symbols, rows)
                    return
                row_data = self._rows.pop(current_idx)
                symbol = self._vt_symbols.pop(current_idx)
                insert_at = target_idx if target_idx < current_idx else target_idx - 1
                self._vt_symbols.insert(insert_at, symbol)
                self._rows.insert(insert_at, row_data)
                self.endMoveRows()
            self.apply_row(target_idx, cells)
