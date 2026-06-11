"""日 K 参考线图例单元测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.quotes.chart.reference_line_legend import ReferenceLineLegendBar


class ReferenceLineLegendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_set_reference_lines_populates_entries(self) -> None:
        legend = ReferenceLineLegendBar()
        legend.set_reference_lines(ref_buy=10.5, ref_sell=11.2, last_price=10.8)

        self.assertTrue(legend.has_entries())
        text = legend._entries["ref_buy"][0].text()
        self.assertIn("支撑锚点", text)
        self.assertIn("10.50", text)

    def test_clear_hides_all_entries(self) -> None:
        legend = ReferenceLineLegendBar()
        legend.set_reference_lines(ref_buy=10.5)
        legend.clear()

        self.assertFalse(legend.has_entries())
        self.assertFalse(legend._entries["ref_buy"][0].isVisible())


if __name__ == "__main__":
    unittest.main()
