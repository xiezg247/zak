"""选股结果洞察面板测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.screener.widgets.screener_insights import ScreenerResultInsights


class ScreenerResultInsightsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_collapsed_shows_inline_summary(self) -> None:
        panel = ScreenerResultInsights()
        panel.show()
        panel.apply(
            [{"vt_symbol": "600519.SSE", "name": "贵州茅台", "industry": "白酒"}],
            {"run_diff": {"new_count": 2, "removed_count": 1}},
        )

        panel.set_expanded(False, persist=False)
        content = panel.findChild(QtWidgets.QWidget, "ScreenerResultInsightsContent")
        self.assertIsNotNone(content)
        self.assertFalse(content.isVisible())
        self.assertTrue(panel._inline_summary.isVisible())
        self.assertIn("新增", panel._inline_summary.text())

    def test_clear_hides_panel(self) -> None:
        panel = ScreenerResultInsights()
        panel.apply([{"vt_symbol": "600519.SSE", "name": "贵州茅台", "industry": "白酒"}], None)
        panel.clear()
        self.assertTrue(panel.isHidden())


if __name__ == "__main__":
    unittest.main()
