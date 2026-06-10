"""表格排序单元格测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.components.sortable_table import SortableTableItem


class SortableTableItemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_numeric_sort(self) -> None:
        low = SortableTableItem("1.00", 1.0)
        high = SortableTableItem("10.00", 10.0)
        self.assertTrue(low < high)

    def test_text_sort(self) -> None:
        a = SortableTableItem("600000", "600000")
        b = SortableTableItem("600519", "600519")
        self.assertTrue(a < b)


if __name__ == "__main__":
    unittest.main()
