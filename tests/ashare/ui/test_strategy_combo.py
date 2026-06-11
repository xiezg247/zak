"""策略回测下拉：中文展示与 class_name 兼容。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.backtest.strategy_combo import StrategyClassCombo, strategy_display_title


class StrategyClassComboTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_display_title_from_registry(self) -> None:
        title = strategy_display_title("AshareDoubleMaStrategy")
        self.assertEqual(title, "A 股双均线")

    def test_combo_shows_title_but_current_text_is_class_name(self) -> None:
        combo = StrategyClassCombo()
        combo.set_strategy_items(["AshareDoubleMaStrategy", "AshareTrendMaStrategy"])

        combo.setCurrentIndex(1)
        self.assertEqual(combo.current_display_title(), "A 股趋势均线")
        self.assertEqual(combo.currentText(), "AshareTrendMaStrategy")
        self.assertEqual(combo.current_class_name(), "AshareTrendMaStrategy")

    def test_find_text_by_class_name(self) -> None:
        combo = StrategyClassCombo()
        combo.set_strategy_items(["AshareDoubleMaStrategy", "AshareTrendMaStrategy"])

        index = combo.findText("AshareTrendMaStrategy")
        self.assertEqual(index, 1)
        combo.setCurrentIndex(index)
        self.assertEqual(combo.current_display_title(), "A 股趋势均线")


if __name__ == "__main__":
    unittest.main()
