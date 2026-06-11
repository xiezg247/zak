"""K 线侧栏折叠设置与面板单元测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.quotes.chart.section import (
    CHART_SIDE_COLLAPSED_WIDTH,
    CHART_SIDE_HANDLE_WIDTH,
    ChartSectionPanel,
    chart_side_collapse_arrow,
)
from vnpy_ashare.ui.quotes.chart.section_settings import (
    load_chart_section_expanded,
    save_chart_section_expanded,
)


class ChartSectionSettingsTests(unittest.TestCase):
    def test_expanded_settings_roundtrip(self) -> None:
        save_chart_section_expanded("测试页", False)
        self.assertFalse(load_chart_section_expanded("测试页"))
        save_chart_section_expanded("测试页", True)
        self.assertTrue(load_chart_section_expanded("测试页"))
        save_chart_section_expanded("自选", False)
        self.assertFalse(load_chart_section_expanded("自选"))
        save_chart_section_expanded("本地", True)
        self.assertTrue(load_chart_section_expanded("本地"))


class ChartSectionPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_collapse_hides_entire_content_and_narrows_panel(self) -> None:
        save_chart_section_expanded("折叠测试", True)
        panel = ChartSectionPanel("折叠测试")
        body = QtWidgets.QWidget()
        body.setMinimumSize(400, 320)
        panel.set_content(body)
        panel.resize(480, 600)
        panel.show()
        QtWidgets.QApplication.processEvents()

        panel.set_expanded(False)
        QtWidgets.QApplication.processEvents()

        self.assertFalse(body.isVisible())
        self.assertFalse(panel._content.isVisible())
        self.assertLessEqual(panel.width(), CHART_SIDE_COLLAPSED_WIDTH + 2)
        self.assertGreaterEqual(panel.width(), CHART_SIDE_HANDLE_WIDTH)

        panel.set_expanded(True)
        QtWidgets.QApplication.processEvents()
        self.assertTrue(body.isVisible())
        self.assertTrue(panel._content.isVisible())

    def test_collapse_arrow_uses_horizontal_chevrons(self) -> None:
        self.assertEqual(
            chart_side_collapse_arrow(True),
            QtCore.Qt.ArrowType.LeftArrow,
        )
        self.assertEqual(
            chart_side_collapse_arrow(False),
            QtCore.Qt.ArrowType.RightArrow,
        )


if __name__ == "__main__":
    unittest.main()
