"""策略回测页：A 股文案与策略列表过滤。"""

from __future__ import annotations

from typing import cast

from vnpy.event import Event
from vnpy.trader.ui import QtCore, QtWidgets
from vnpy_ctabacktester.ui.widget import BacktesterManager as VnpyBacktesterManager

from strategies.ashare_template import AShareTemplate
from strategies.registry import (
    format_missing_strategy_guide,
    format_strategy_guide,
    get_strategy_meta,
)
from vnpy_ashare.ai.session_context import BacktestSummary, set_backtest_summary
from vnpy_ashare.config import ASHARE_BACKTEST_DEFAULTS, format_decimal_field
from vnpy_ashare.ui.backtest_chart import AshareBacktesterChart
from vnpy_ashare.ui.styles import NAV_MUTED_COLOR, PANEL_BG

_LABEL_MAP: dict[str, str] = {
    "本地代码": "股票代码",
    "合约乘数": "每股乘数",
}


class BacktesterWidget(VnpyBacktesterManager):
    """vnpy CTA 回测 Widget 的 A 股包装：标题、字段文案、策略下拉过滤。"""

    def init_ui(self) -> None:
        super().init_ui()
        self.setWindowTitle("策略回测")
        self._localize_labels()
        self.symbol_line.setPlaceholderText("如 600519.SSE / 000001.SZSE")
        self._replace_chart_widget()
        self._install_strategy_guide()

    def _replace_chart_widget(self) -> None:
        old_chart = self.chart
        new_chart = AshareBacktesterChart()
        parent = old_chart.parentWidget()
        if parent is not None:
            layout = parent.layout()
            if layout is not None:
                layout.replaceWidget(old_chart, new_chart)
        old_chart.deleteLater()
        self.chart = new_chart

    def _install_strategy_guide(self) -> None:
        frame = QtWidgets.QFrame()
        frame.setObjectName("StrategyGuideFrame")
        frame.setStyleSheet(
            f"QFrame#StrategyGuideFrame {{"
            f"background-color: {PANEL_BG};"
            f"border: 1px solid #2a2a2a;"
            f"border-radius: 4px;"
            f"}}"
        )

        self.strategy_guide = QtWidgets.QLabel()
        self.strategy_guide.setObjectName("StrategyGuide")
        self.strategy_guide.setWordWrap(True)
        self.strategy_guide.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.strategy_guide.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft
        )
        self.strategy_guide.setStyleSheet(
            f"color: {NAV_MUTED_COLOR}; font-size: 12px; padding: 8px;"
        )

        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.strategy_guide)

        left_vbox = self._left_settings_vbox()
        if left_vbox is not None:
            left_vbox.insertWidget(1, frame)

        self.class_combo.currentTextChanged.connect(self._update_strategy_guide)
        self._update_strategy_guide(self.class_combo.currentText())

    def _left_settings_vbox(self) -> QtWidgets.QVBoxLayout | None:
        root = self.layout()
        if root is None or root.count() == 0:
            return None
        left_widget = root.itemAt(0).widget()
        if left_widget is None:
            return None
        left_hbox = left_widget.layout()
        if left_hbox is None or left_hbox.count() == 0:
            return None
        item = left_hbox.itemAt(0)
        if item is None:
            return None
        layout = item.layout()
        if isinstance(layout, QtWidgets.QVBoxLayout):
            return layout
        return None

    def _update_strategy_guide(self, class_name: str) -> None:
        if not hasattr(self, "strategy_guide"):
            return
        name = class_name.strip()
        if not name:
            self.strategy_guide.setText(
                '<p style="color:#8a8a8a;">选择策略后显示说明与适用场景。</p>'
            )
            return
        meta = get_strategy_meta(name)
        if meta is None:
            self.strategy_guide.setText(format_missing_strategy_guide(name))
            return
        self.strategy_guide.setText(format_strategy_guide(meta))

    def init_strategy_settings(self) -> None:
        super().init_strategy_settings()
        ashare_names = sorted(
            name
            for name, cls in self.backtester_engine.classes.items()
            if issubclass(cls, AShareTemplate) and cls is not AShareTemplate
        )
        if not ashare_names:
            self.class_names = []
            self.class_combo.clear()
            self.write_log("未发现 A 股策略，请检查 strategies/ 目录下的策略导入是否正常。")
            return

        self.class_names = ashare_names
        self.class_combo.clear()
        self.class_combo.addItems(ashare_names)
        self._update_strategy_guide(self.class_combo.currentText())

    def load_backtesting_setting(self) -> None:
        super().load_backtesting_setting()
        if not self.symbol_line.text().strip():
            defaults = ASHARE_BACKTEST_DEFAULTS
            self.symbol_line.setText(str(defaults["vt_symbol"]))
            self.rate_line.setText(format_decimal_field(defaults["rate"], places=6))
            self.slippage_line.setText(format_decimal_field(defaults["slippage"], places=4))
            self.size_line.setText(str(defaults["size"]))
            self.pricetick_line.setText(format_decimal_field(defaults["pricetick"], places=4))
            self.capital_line.setText(str(defaults["capital"]))
        else:
            self._normalize_decimal_fields()
        self._update_strategy_guide(self.class_combo.currentText())

    def _normalize_decimal_fields(self) -> None:
        for line, places in (
            (self.rate_line, 6),
            (self.slippage_line, 4),
            (self.pricetick_line, 4),
        ):
            text = line.text().strip()
            if not text:
                continue
            try:
                line.setText(format_decimal_field(float(text), places=places))
            except ValueError:
                continue

    def apply_vt_symbol(self, vt_symbol: str, *, source_page: str = "") -> None:
        """由看盘页跳转时预填股票代码，不触发回测。"""
        symbol = vt_symbol.strip()
        if "." not in symbol:
            return
        self.symbol_line.setText(symbol)
        if source_page:
            self.write_log(f"已从{source_page}带入股票代码：{symbol}")
        else:
            self.write_log(f"已带入股票代码：{symbol}")

    def _localize_labels(self) -> None:
        for label in self.findChildren(QtWidgets.QLabel):
            text = label.text()
            if text in _LABEL_MAP:
                label.setText(_LABEL_MAP[text])

    def process_backtesting_finished_event(self, event: Event) -> None:
        super().process_backtesting_finished_event(event)
        statistics = self.backtester_engine.get_result_statistics()
        if not statistics:
            return
        start = cast(QtCore.QDateTime, self.start_date_edit.dateTime()).toPython()
        end = cast(QtCore.QDateTime, self.end_date_edit.dateTime()).toPython()
        set_backtest_summary(
            BacktestSummary(
                strategy=self.class_combo.currentText(),
                vt_symbol=self.symbol_line.text().strip(),
                interval=self.interval_combo.currentText(),
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                statistics=dict(statistics),
            )
        )
