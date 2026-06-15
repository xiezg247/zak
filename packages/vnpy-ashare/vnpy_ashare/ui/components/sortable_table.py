"""表格排序单元格。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets


class SortableTableItem(QtWidgets.QTableWidgetItem):
    """按 sort_key 排序，展示 text。"""

    def __init__(self, text: str, sort_key: float | str) -> None:
        super().__init__(text)
        self._sort_key = sort_key

    def __lt__(self, other: object) -> bool:
        if isinstance(other, SortableTableItem):
            left = self._sort_key
            right = other._sort_key
            if type(left) is type(right) and left != right:
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return float(left) < float(right)
                if isinstance(left, str) and isinstance(right, str):
                    return left < right
            return str(left) < str(right)
        return super().__lt__(other)

    def update_sort_key(self, sort_key: float | str) -> None:
        self._sort_key = sort_key
