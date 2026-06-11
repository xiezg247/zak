"""自动选股页单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.screener.pages.auto_screener_page import AutoScreenerPageWidget


class AutoScreenerPageWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_page_builds_with_output_panel_and_empty_result_state(self) -> None:
        page = AutoScreenerPageWidget(MagicMock(), MagicMock())

        self.assertIsNotNone(page.run_output_panel)
        self.assertFalse(page.result_table.isVisible())
        self.assertEqual(page.result_table.rowCount(), 0)
        self.assertIn("试跑", page._empty_result_label.text())

    def test_format_result_summary_includes_hit_count(self) -> None:
        page = AutoScreenerPageWidget(MagicMock(), MagicMock())
        summary = page._format_result_summary(
            condition="盘中多因子",
            row_count=5,
            total_scanned=100,
            source="redis",
            updated_at="2026-06-09",
        )
        self.assertIn("命中 5 条", summary)
        self.assertIn("盘中多因子", summary)


if __name__ == "__main__":
    unittest.main()
