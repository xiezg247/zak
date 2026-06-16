"""选股结果操作条测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.screener.widgets.screener_toolbars import ScreenerResultActionBar


class ScreenerResultActionBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_hidden_until_results_available(self) -> None:
        bar = ScreenerResultActionBar()

        self.assertTrue(bar.isHidden())
        bar.set_has_results(True)
        self.assertFalse(bar.isHidden())
        bar.set_has_results(False)
        self.assertTrue(bar.isHidden())


if __name__ == "__main__":
    unittest.main()
