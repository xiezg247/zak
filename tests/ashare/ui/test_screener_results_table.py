"""选股结果表格单元测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.screener.screener_results_table import (
    apply_screener_results_view,
    configure_screener_results_table,
)


class ScreenerResultsTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_empty_state_hides_table_without_default_selection(self) -> None:
        label = QtWidgets.QLabel("empty")
        table = QtWidgets.QTableWidget(0, 0)
        configure_screener_results_table(table)

        apply_screener_results_view(table, [], [], empty_label=label)

        self.assertTrue(table.isHidden())
        self.assertTrue(label.isVisible())
        self.assertEqual(table.rowCount(), 0)
        self.assertIsNone(table.currentItem())

    def test_populated_results_show_table_and_clear_selection(self) -> None:
        label = QtWidgets.QLabel("empty")
        table = QtWidgets.QTableWidget(0, 0)
        configure_screener_results_table(table)
        rows = [{"vt_symbol": "000001.SZSE", "name": "平安银行", "change_pct": 1.2}]
        columns = [("vt_symbol", "代码"), ("name", "名称"), ("change_pct", "涨幅")]

        apply_screener_results_view(table, rows, columns, empty_label=label)

        self.assertTrue(table.isVisible())
        self.assertTrue(label.isHidden())
        self.assertEqual(table.rowCount(), 1)
        self.assertIsNone(table.currentItem())


if __name__ == "__main__":
    unittest.main()
