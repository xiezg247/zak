"""QuoteTableModel 测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.constant import Exchange

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.models import StockItem
from vnpy_ashare.ui.quotes.table.model import QuoteTableModel


class QuoteTableModelTests(unittest.TestCase):
    def test_apply_cell_and_stock_at_row(self) -> None:
        model = QuoteTableModel()
        model.set_headers(["代码", "名称"])
        model.set_row_count(1)
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="茅台")
        model.apply_cell(0, 0, "600519", sort_key="600519", stock_item=item)
        model.apply_cell(0, 1, "茅台", sort_key="茅台")

        self.assertEqual(model.stock_at_row(0), item)
        index = model.index(0, 0)
        self.assertEqual(model.data(index), "600519")

    def test_set_rows_batch(self) -> None:
        model = QuoteTableModel()
        model.set_headers(["代码", "名称"])
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="茅台")
        from vnpy_ashare.ui.quotes.table.model import QuoteCell

        model.set_rows(
            [
                [QuoteCell(text="600519", stock_item=item), QuoteCell(text="茅台")],
                [QuoteCell(text="000001"), QuoteCell(text="平安")],
            ]
        )
        self.assertEqual(model.row_count(), 2)
        self.assertEqual(model.stock_at_row(0), item)

    def test_append_rows(self) -> None:
        from vnpy_ashare.ui.quotes.table.model import QuoteCell

        model = QuoteTableModel()
        model.set_headers(["代码"])
        model.set_rows([[QuoteCell(text="600519")]])
        model.append_rows([[QuoteCell(text="000001")]])
        self.assertEqual(model.row_count(), 2)
        self.assertEqual(model.data(model.index(1, 0)), "000001")

    def test_sort_by_sort_key(self) -> None:
        model = QuoteTableModel()
        model.set_headers(["分数"])
        model.set_row_count(2)
        model.apply_cell(0, 0, "低", sort_key=10)
        model.apply_cell(1, 0, "高", sort_key=90)

        from vnpy.trader.ui import QtCore

        model.sort(0, QtCore.Qt.SortOrder.DescendingOrder)
        self.assertEqual(model.data(model.index(0, 0)), "高")


if __name__ == "__main__":
    unittest.main()
