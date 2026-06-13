"""选股结果表格单元测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.screener.widgets.screener_results_table import (
    _format_cell_text,
    apply_screener_results_view,
    configure_screener_results_table,
    populate_screener_results_table,
)


class ScreenerResultsTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_configure_sets_screener_object_name(self) -> None:
        table = QtWidgets.QTableWidget(0, 0)
        configure_screener_results_table(table)
        self.assertEqual(table.objectName(), "ScreenerResultsTable")

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
        rows = [{"vt_symbol": "000001.SZSE", "symbol": "000001", "name": "平安银行", "change_pct": 1.2}]
        columns = [("vt_symbol", "合约"), ("symbol", "代码"), ("name", "名称"), ("change_pct", "涨幅")]

        apply_screener_results_view(table, rows, columns, empty_label=label)

        self.assertTrue(table.isVisible())
        self.assertTrue(label.isHidden())
        self.assertEqual(table.rowCount(), 1)
        self.assertIsNone(table.currentItem())

    def test_populate_adds_rank_and_formats_percent(self) -> None:
        table = QtWidgets.QTableWidget(0, 0)
        configure_screener_results_table(table)
        rows = [
            {"symbol": "600000", "name": "浦发", "change_pct": 2.35, "hit_reason": "放量突破"},
            {"symbol": "600001", "name": "邯郸", "change_pct": -1.1, "hit_reason": "均线多头"},
        ]
        columns = [("symbol", "代码"), ("name", "名称"), ("change_pct", "涨幅%"), ("hit_reason", "入选原因")]

        populate_screener_results_table(table, rows, columns)

        self.assertEqual(table.columnCount(), 6)
        self.assertEqual(table.horizontalHeaderItem(1).text(), "#")
        self.assertEqual(table.item(0, 1).text(), "1")
        self.assertEqual(table.item(1, 1).text(), "2")
        self.assertEqual(table.item(0, 4).text(), "+2.35%")
        self.assertEqual(
            table.item(0, 4).textAlignment(),
            int(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter),
        )
        self.assertEqual(table.item(0, 5).toolTip(), "放量突破")

    def test_format_cell_text(self) -> None:
        self.assertEqual(_format_cell_text("change_pct", 1.2), "+1.20%")
        self.assertEqual(_format_cell_text("turnover_rate", 3.5), "3.50%")
        self.assertEqual(_format_cell_text("name", ""), "—")


if __name__ == "__main__":
    unittest.main()
