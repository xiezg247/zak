"""回测图表主题测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtGui, QtWidgets

from vnpy_ashare.ui.backtest.chart.backtest_chart import AshareBacktesterChart, apply_backtest_chart_theme
from vnpy_common.ui.theme.manager import ThemeManager, theme_manager
from vnpy_common.ui.theme.build_chart import chart_palette
from vnpy_common.ui.theme.tokens import LIGHT_TOKENS


class BacktestChartThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self) -> None:
        ThemeManager._instance = None
        theme_manager().set_theme("system", persist=False)

    def test_backtest_chart_uses_light_background(self) -> None:
        chart = AshareBacktesterChart()
        apply_backtest_chart_theme(chart, tokens=LIGHT_TOKENS)
        palette = chart_palette(LIGHT_TOKENS)
        bg = chart.backgroundBrush().color()
        expected = QtGui.QColor(palette.panel_bg)
        self.assertEqual(bg.name(), expected.name())
        self.assertNotEqual(bg.name(), "#000000")

    def test_theme_switch_refreshes_chart_background(self) -> None:
        chart = AshareBacktesterChart()
        theme_manager().set_theme("dark", persist=False)
        apply_backtest_chart_theme(chart, tokens=theme_manager().tokens())
        dark_bg = chart.backgroundBrush().color().name()

        apply_backtest_chart_theme(chart, tokens=LIGHT_TOKENS)
        chart._on_theme_changed(LIGHT_TOKENS)
        light_bg = chart.backgroundBrush().color().name()

        self.assertNotEqual(dark_bg, light_bg)
        self.assertEqual(light_bg, QtGui.QColor(chart_palette(LIGHT_TOKENS).panel_bg).name())


if __name__ == "__main__":
    unittest.main()
