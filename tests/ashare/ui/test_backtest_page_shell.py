"""策略回测页布局测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.backtest.pages.backtest_page_shell import BacktestPageShell


class _BacktestPageStub(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.class_combo = QtWidgets.QComboBox()
        self.symbol_line = QtWidgets.QLineEdit()
        self.interval_combo = QtWidgets.QComboBox()
        self.start_date_edit = QtWidgets.QDateEdit()
        self.end_date_edit = QtWidgets.QDateEdit()
        self.rate_line = QtWidgets.QLineEdit()
        self.slippage_line = QtWidgets.QLineEdit()
        self.size_line = QtWidgets.QLineEdit()
        self.pricetick_line = QtWidgets.QLineEdit()
        self.capital_line = QtWidgets.QLineEdit()
        self.run_button = QtWidgets.QPushButton("开始回测")
        self.download_button = QtWidgets.QPushButton("下载数据")
        self.optimization_button = QtWidgets.QPushButton("参数优化")
        self.result_button = QtWidgets.QPushButton("优化结果")
        self.trade_button = QtWidgets.QPushButton("成交记录")
        self.order_button = QtWidgets.QPushButton("委托记录")
        self.daily_button = QtWidgets.QPushButton("每日盈亏")
        self.candle_button = QtWidgets.QPushButton("K 线图表")
        self.edit_button = QtWidgets.QPushButton("代码编辑")
        self.reload_button = QtWidgets.QPushButton("策略重载")
        self.statistics_monitor = QtWidgets.QTableWidget(2, 1)
        self.log_monitor = QtWidgets.QTextEdit()
        self.chart = QtWidgets.QWidget()
        self.strategy_guide_button = QtWidgets.QPushButton("说明")
        self.ask_ai_button = QtWidgets.QPushButton("问 AI")

    def _install_strategy_guide(self, form: QtWidgets.QFormLayout) -> None:
        form.addRow("交易策略", self.class_combo)


class BacktestPageShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_build_installs_vertical_layout_with_splitters(self) -> None:
        page = _BacktestPageStub()
        BacktestPageShell(page).build()
        layout = page.layout()
        self.assertIsNotNone(layout)
        self.assertGreaterEqual(layout.count(), 3)
        self.assertTrue(page.log_monitor.isReadOnly())
        self.assertEqual(page.run_button.objectName(), "PrimaryRunButton")


if __name__ == "__main__":
    unittest.main()
