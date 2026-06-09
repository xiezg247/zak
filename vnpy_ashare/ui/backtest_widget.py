"""策略回测页：A 股文案与策略列表过滤。"""

from __future__ import annotations

from typing import cast

from vnpy.event import Event
from vnpy.trader.ui import QtCore, QtWidgets
from vnpy_ctabacktester.ui.widget import BacktesterManager as VnpyBacktesterManager

from strategies.registry import (
    format_missing_strategy_guide,
    format_strategy_guide,
    get_strategy_meta,
)
from vnpy_ashare.ai.backtest_context import (
    build_backtest_ai_prompt,
    connect_backtest_context_sync,
    format_backtest_summary_text,
    sync_backtest_page_context,
)
from vnpy_ashare.ai.session_context import BacktestSummary, get_backtest_summary
from vnpy_ashare.events import EVENT_ASK_AI, AskAiRequest
from vnpy_ashare.backtest_strategy_filter import filter_ashare_strategy_names
from vnpy_ashare.config import ASHARE_BACKTEST_DEFAULTS, format_decimal_field
from vnpy_ashare.ui.backtest_chart import AshareBacktesterChart
from vnpy_ashare.ui.styles import NAV_MUTED_COLOR, apply_toolbar_combo_style

_LABEL_MAP: dict[str, str] = {
    "本地代码": "股票代码",
    "合约乘数": "每股乘数",
}

_LOG_MAP: dict[str, str] = {
    "初始化CTA回测引擎": "初始化策略回测引擎",
    "策略文件重载刷新完成": "策略文件重载完成",
}


class StrategyGuideDialog(QtWidgets.QDialog):
    """策略说明弹窗。"""

    def __init__(self, title: str, html: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(480, 520)

        label = QtWidgets.QLabel(html)
        label.setWordWrap(True)
        label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
        label.setStyleSheet(f"color: {NAV_MUTED_COLOR}; font-size: 12px; padding: 4px;")

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(label)

        close_button = QtWidgets.QPushButton("关闭")
        close_button.setObjectName("SecondaryButton")
        close_button.clicked.connect(self.accept)

        footer = QtWidgets.QHBoxLayout()
        footer.addStretch()
        footer.addWidget(close_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(scroll, stretch=1)
        layout.addLayout(footer)


class BacktesterWidget(VnpyBacktesterManager):
    """vnpy CTA 回测 Widget 的 A 股包装：标题、字段文案、策略下拉过滤。"""

    def init_ui(self) -> None:
        super().init_ui()
        self.setWindowTitle("策略回测")
        self._localize_labels()
        self.symbol_line.setPlaceholderText("如 600519.SSE / 000001.SZSE")
        self._replace_chart_widget()
        apply_toolbar_combo_style(self.class_combo)
        apply_toolbar_combo_style(self.interval_combo)
        self._install_strategy_guide()
        self._install_ask_ai_button()
        connect_backtest_context_sync(self)

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass

    def _install_ask_ai_button(self) -> None:
        self.ask_ai_button = QtWidgets.QPushButton("问 AI")
        self.ask_ai_button.setObjectName("SecondaryButton")
        self.ask_ai_button.setToolTip("打开 AI 助手解读最近一次回测")
        self.ask_ai_button.clicked.connect(self._ask_ai_for_backtest)
        left_vbox = self._left_settings_vbox()
        if left_vbox is not None:
            left_vbox.addWidget(self.ask_ai_button)

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
        self._strategy_guide_html = ""
        self.strategy_guide_button = QtWidgets.QPushButton("说明")
        self.strategy_guide_button.setObjectName("SecondaryButton")
        self.strategy_guide_button.setFixedWidth(56)
        self.strategy_guide_button.setToolTip("查看当前策略的适用场景与参数说明")
        self.strategy_guide_button.clicked.connect(self._show_strategy_guide_dialog)
        self.strategy_guide_button.setEnabled(False)

        form = self._settings_form()
        if form is not None:
            for row in range(form.rowCount()):
                field = form.itemAt(row, QtWidgets.QFormLayout.ItemRole.FieldRole)
                if field is None or field.widget() is not self.class_combo:
                    continue
                row_layout = QtWidgets.QHBoxLayout()
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(8)
                form.removeWidget(self.class_combo)
                row_layout.addWidget(self.class_combo, stretch=1)
                row_layout.addWidget(self.strategy_guide_button)
                container = QtWidgets.QWidget()
                container.setLayout(row_layout)
                form.setWidget(row, QtWidgets.QFormLayout.ItemRole.FieldRole, container)
                break

        self.class_combo.currentTextChanged.connect(self._on_strategy_changed)
        self._on_strategy_changed(self.class_combo.currentText())

    def _settings_form(self) -> QtWidgets.QFormLayout | None:
        left_vbox = self._left_settings_vbox()
        if left_vbox is None or left_vbox.count() == 0:
            return None
        layout = left_vbox.itemAt(0).layout()
        if isinstance(layout, QtWidgets.QFormLayout):
            return layout
        return None

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

    def _build_strategy_guide_html(self, class_name: str) -> str:
        name = class_name.strip()
        if not name:
            return '<p style="color:#8a8a8a;">选择策略后显示说明与适用场景。</p>'
        meta = get_strategy_meta(name)
        if meta is None:
            return format_missing_strategy_guide(name)
        return format_strategy_guide(meta)

    def _on_strategy_changed(self, class_name: str) -> None:
        self._strategy_guide_html = self._build_strategy_guide_html(class_name)
        if hasattr(self, "strategy_guide_button"):
            self.strategy_guide_button.setEnabled(bool(class_name.strip()))

    def _show_strategy_guide_dialog(self) -> None:
        class_name = self.class_combo.currentText().strip()
        if not class_name:
            return
        meta = get_strategy_meta(class_name)
        title = meta.title if meta else class_name
        dialog = StrategyGuideDialog(title, self._strategy_guide_html, self)
        dialog.exec()

    def _ashare_strategy_names(self) -> list[str]:
        return filter_ashare_strategy_names(self.backtester_engine.classes)

    def write_log(self, msg: str) -> None:
        super().write_log(_LOG_MAP.get(msg, msg))

    def _ensure_class_combo_selection(self) -> None:
        if self.class_combo.currentIndex() >= 0 or not self.class_names:
            return
        default_name = str(ASHARE_BACKTEST_DEFAULTS["class_name"])
        index = self.class_combo.findText(default_name)
        if index < 0:
            index = 0
        self.class_combo.setCurrentIndex(index)

    def init_strategy_settings(self) -> None:
        super().init_strategy_settings()
        ashare_names = self._ashare_strategy_names()
        if not ashare_names:
            self.class_names = []
            self.class_combo.clear()
            self.write_log(
                "未发现 A 股策略，请检查项目 strategies/ 目录及策略类是否继承 AShareTemplate。"
            )
            return

        self.class_names = ashare_names
        self.settings = {
            name: self.settings[name]
            for name in ashare_names
            if name in self.settings
        }
        self.class_combo.clear()
        self.class_combo.addItems(ashare_names)
        self._ensure_class_combo_selection()
        self._on_strategy_changed(self.class_combo.currentText())

    def load_backtesting_setting(self) -> None:
        super().load_backtesting_setting()
        self._ensure_class_combo_selection()
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
        self._on_strategy_changed(self.class_combo.currentText())

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

    def _get_last_backtest_summary(self) -> dict | None:
        from vnpy_ashare.engine import APP_NAME, AshareEngine

        engine = self.main_engine.get_engine(APP_NAME)
        if isinstance(engine, AshareEngine):
            return engine.backtest_service.get_last_summary()
        return get_backtest_summary()

    def _ask_ai_for_backtest(self) -> None:
        summary = self._get_last_backtest_summary()
        if not summary:
            QtWidgets.QMessageBox.information(self, "提示", "请先完成一次回测")
            return
        sync_backtest_page_context(self, self.main_engine)
        if self.event_engine is None:
            return
        self.event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(
                    prompt=build_backtest_ai_prompt(summary),
                    source_page="策略回测",
                    use_full_page=True,
                    new_session=True,
                ),
            )
        )

    def _write_backtest_summary_log(self, summary: dict) -> None:
        self.write_log("—— 回测摘要 ——")
        for line in format_backtest_summary_text(summary).splitlines():
            text = line.strip()
            if text:
                self.write_log(text)
        self.write_log("如需 AI 解读，请点击「问 AI」")

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
        summary = BacktestSummary(
            strategy=self.class_combo.currentText(),
            vt_symbol=self.symbol_line.text().strip(),
            interval=self.interval_combo.currentText(),
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            statistics=dict(statistics),
        )
        summary_dict = summary.to_dict()
        self._write_backtest_summary_log(summary_dict)
        from vnpy_ashare.engine import APP_NAME, AshareEngine

        engine = self.main_engine.get_engine(APP_NAME)
        if isinstance(engine, AshareEngine):
            engine.backtest_service.persist_summary(summary_dict, source="single")
        else:
            from vnpy_ashare.ai.session_context import set_backtest_summary

            set_backtest_summary(summary)
