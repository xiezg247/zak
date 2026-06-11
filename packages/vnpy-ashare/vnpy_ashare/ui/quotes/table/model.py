"""行情表格 Model（QAbstractTableModel，替代 QTableWidget 单元格）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtGui

if TYPE_CHECKING:
    from vnpy_ashare.domain.symbols import StockItem

_INVALID_PARENT = QtCore.QModelIndex()


@dataclass
class QuoteCell:
    text: str = ""
    sort_key: float | str = ""
    color: str | None = None
    stock_item: StockItem | None = None
    tooltip: str | None = None


class QuoteTableModel(QtCore.QAbstractTableModel):
    """看盘页行情表格数据模型。"""

    SortKeyRole = QtCore.Qt.ItemDataRole.UserRole + 1
    StockItemRole = QtCore.Qt.ItemDataRole.UserRole

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._headers: list[str] = []
        self._rows: list[list[QuoteCell]] = []

    def set_headers(self, headers: list[str]) -> None:
        if headers == self._headers:
            return
        self.beginResetModel()
        self._headers = list(headers)
        self._ensure_row_widths()
        self.endResetModel()

    def headers(self) -> list[str]:
        return list(self._headers)

    def set_row_count(self, count: int) -> None:
        count = max(0, count)
        if count == len(self._rows):
            return
        self.beginResetModel()
        if count < len(self._rows):
            self._rows = self._rows[:count]
        else:
            self._ensure_row_widths()
            empty_row = [QuoteCell() for _ in range(len(self._headers))]
            for _ in range(len(self._rows), count):
                self._rows.append([QuoteCell(cell.text, cell.sort_key, cell.color, cell.stock_item) for cell in empty_row])
        self.endResetModel()

    def set_rows(self, rows: list[list[QuoteCell]]) -> None:
        """批量替换全部行（单次 model reset，避免逐格 dataChanged）。"""
        self.beginResetModel()
        self._rows = [list(row) for row in rows]
        self._ensure_row_widths()
        self.endResetModel()

    def append_rows(self, rows: list[list[QuoteCell]]) -> None:
        """在末尾追加行（下拉分页）。"""
        if not rows:
            return
        start = len(self._rows)
        end = start + len(rows) - 1
        self.beginInsertRows(QtCore.QModelIndex(), start, end)
        for row in rows:
            self._rows.append(list(row))
        self._ensure_row_widths()
        self.endInsertRows()

    def row_count(self) -> int:
        return len(self._rows)

    def column_count(self) -> int:
        return len(self._headers)

    def stock_at_row(self, row: int) -> StockItem | None:
        if row < 0 or row >= len(self._rows) or not self._rows[row]:
            return None
        return self._rows[row][0].stock_item

    def apply_cell(
        self,
        row: int,
        column: int,
        text: str,
        *,
        sort_key: float | str | None = None,
        color: str | None = None,
        stock_item: StockItem | None = None,
        tooltip: str | None = None,
        replace: bool = False,
    ) -> None:
        if row < 0 or column < 0:
            return
        self._ensure_rows(row + 1)
        self._ensure_columns(column + 1)

        cell = self._rows[row][column]
        if replace:
            cell = QuoteCell()
            self._rows[row][column] = cell

        changed_roles: list[int] = []
        if cell.text != text:
            cell.text = text
            changed_roles.append(QtCore.Qt.ItemDataRole.DisplayRole)
        if sort_key is not None and cell.sort_key != sort_key:
            cell.sort_key = sort_key
            changed_roles.append(self.SortKeyRole)
        if color != cell.color:
            cell.color = color
            changed_roles.append(QtCore.Qt.ItemDataRole.ForegroundRole)
        if stock_item is not None and cell.stock_item is not stock_item:
            cell.stock_item = stock_item
            changed_roles.append(self.StockItemRole)
        if tooltip is not None and cell.tooltip != tooltip:
            cell.tooltip = tooltip
            changed_roles.append(QtCore.Qt.ItemDataRole.ToolTipRole)

        if changed_roles:
            top_left = self.index(row, column)
            for role in changed_roles:
                self.dataChanged.emit(top_left, top_left, [role])

    def _ensure_rows(self, count: int) -> None:
        if count <= len(self._rows):
            return
        self.beginInsertRows(QtCore.QModelIndex(), len(self._rows), count - 1)
        width = max(len(self._headers), 1)
        for _ in range(len(self._rows), count):
            self._rows.append([QuoteCell() for _ in range(width)])
        self.endInsertRows()

    def _ensure_columns(self, count: int) -> None:
        if count <= len(self._headers):
            for row in self._rows:
                while len(row) < count:
                    row.append(QuoteCell())
            return
        self.beginInsertColumns(QtCore.QModelIndex(), len(self._headers), count - 1)
        for _ in range(len(self._headers), count):
            self._headers.append("")
        for row in self._rows:
            while len(row) < count:
                row.append(QuoteCell())
        self.endInsertColumns()

    def _ensure_row_widths(self) -> None:
        width = len(self._headers)
        for row in self._rows:
            while len(row) < width:
                row.append(QuoteCell())
            if len(row) > width:
                del row[width:]

    def rowCount(self, parent: QtCore.QModelIndex = _INVALID_PARENT) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QtCore.QModelIndex = _INVALID_PARENT) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._headers)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> object | None:  # noqa: N802
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row >= len(self._rows) or col >= len(self._rows[row]):
            return None
        cell = self._rows[row][col]
        if role in (QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.EditRole):
            return cell.text
        if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            return int(QtCore.Qt.AlignmentFlag.AlignCenter)
        if role == QtCore.Qt.ItemDataRole.ForegroundRole and cell.color:
            return QtGui.QColor(cell.color)
        if role == self.StockItemRole:
            return cell.stock_item
        if role == self.SortKeyRole:
            return cell.sort_key
        if role == QtCore.Qt.ItemDataRole.ToolTipRole:
            return cell.tooltip or None
        return None

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int = QtCore.Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == QtCore.Qt.Orientation.Horizontal and 0 <= section < len(self._headers):
            return self._headers[section]
        return None

    def flags(self, index: QtCore.Qt.QModelIndex) -> QtCore.Qt.ItemFlag:  # noqa: N802
        if not index.isValid():
            return QtCore.Qt.ItemFlag.NoItemFlags
        return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

    def sort(self, column: int, order: QtCore.Qt.SortOrder = QtCore.Qt.SortOrder.AscendingOrder) -> None:  # noqa: N802
        if column < 0 or not self._rows:
            return

        reverse = order == QtCore.Qt.SortOrder.DescendingOrder

        def sort_key(row: list[QuoteCell]) -> float | str:
            if column >= len(row):
                return ""
            return row[column].sort_key if row[column].sort_key != "" else row[column].text

        self.layoutAboutToBeChanged.emit()
        self._rows.sort(key=sort_key, reverse=reverse)
        self.layoutChanged.emit()
