"""策略选股页构建测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.screener.pages.screener_page import ScreenerPageWidget


class ScreenerPageWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_page_builds_with_status_pattern_and_filters(self) -> None:
        page = ScreenerPageWidget(MagicMock(), MagicMock())

        self.assertIsNotNone(page.data_status_bar)
        self.assertIsNotNone(page.result_insights)
        self.assertIsNotNone(page.hard_filter_panel)
        panel = page.hard_filter_panel
        self.assertTrue(panel.exclude_new_listing_check.isEnabled())
        self.assertTrue(panel.exclude_st_check.isEnabled())
        self.assertGreater(page.pattern_combo.count(), 0)
        self.assertIsNotNone(page.reference_peer_btn)


if __name__ == "__main__":
    unittest.main()
