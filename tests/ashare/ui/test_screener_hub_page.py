"""选股 hub 页构建测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.screener.pages.screener_hub_page import ScreenerHubPageWidget


class ScreenerHubPageWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_hub_builds_with_condition_and_recipe_tabs(self) -> None:
        page = ScreenerHubPageWidget(MagicMock(), MagicMock())

        self.assertEqual(page._tabs.count(), 2)
        self.assertEqual(page._tabs.tabText(0), "条件选股")
        self.assertEqual(page._tabs.tabText(1), "多因子配方")
        self.assertIsNotNone(page.condition_page.data_status_bar)
        self.assertIsNotNone(page.recipe_page.run_output_panel)

    def test_select_tab_switches_current_index(self) -> None:
        page = ScreenerHubPageWidget(MagicMock(), MagicMock())

        page.select_tab("recipe")
        self.assertEqual(page._tabs.currentIndex(), 1)
        page.select_tab("condition")
        self.assertEqual(page._tabs.currentIndex(), 0)


if __name__ == "__main__":
    unittest.main()
