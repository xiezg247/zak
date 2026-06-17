"""策略回测页：A 股文案与策略列表过滤。"""

from __future__ import annotations

import platform
import shutil
import subprocess
from datetime import datetime, timedelta
from typing import cast

from vnpy.event import Event
from vnpy.trader.constant import Interval
from vnpy.trader.ui import QtCore, QtWidgets
from vnpy_ctabacktester.ui.widget import (
    BacktesterManager as VnpyBacktesterManager,
)
from vnpy_ctabacktester.ui.widget import (
    BacktestingOrderMonitor,
    BacktestingResultDialog,
    BacktestingTradeMonitor,
    CandleChartDialog,
    DailyResultMonitor,
)

from strategies.registry import (
    format_missing_strategy_guide,
    format_strategy_guide,
    get_strategy_meta,
)
from vnpy_ashare.ai.context import (
    BacktestSummary,
    build_backtest_ai_prompt,
    format_backtest_summary_text,
    get_backtest_summary_dict,
    sync_backtest_page_context,
)
from vnpy_ashare.app.engine_access import get_backtest_service
from vnpy_ashare.app.events import EVENT_ASK_AI, AskAiRequest
from vnpy_ashare.backtest.strategy_filter import filter_ashare_strategy_names
from vnpy_ashare.config import ASHARE_BACKTEST_DEFAULTS, format_decimal_field
from vnpy_ashare.ui.backtest.chart.backtest_chart import AshareBacktesterChart, AshareStatisticsMonitor
from vnpy_ashare.ui.backtest.pages.backtest_page_shell import BacktestPageShell
from vnpy_ashare.ui.backtest.strategy_combo import StrategyClassCombo
from vnpy_ashare.ui.styles import (
    apply_toolbar_combo_style,
    apply_vnpy_page_style,
    style_vnpy_form_inputs,
)
from vnpy_common.ui.feedback import TaskGuard, page_notify
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.build_extra import build_settings_stylesheet
from vnpy_common.ui.theme.html_palette import html_palette

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
        label.setObjectName("SettingsHint")
        label.setWordWrap(True)
        label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)

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
        theme_manager().bind_stylesheet(self, extra=build_settings_stylesheet)


class BacktesterWidget(VnpyBacktesterManager):
    """A 股策略回测页：自研布局 + vnpy 回测引擎。"""

    def init_ui(self) -> None:
        self._create_form_controls()
        self._create_action_buttons()
        self._create_result_panels()
        self._create_dialogs()
        self._prepare_strategy_guide_button()
        self._prepare_ask_ai_button()
        BacktestPageShell(self).build()
        self._task_guard = TaskGuard(self._toast)
        self._backtest_task_kind: str | None = None
        self._thread_poll = QtCore.QTimer(self)
        self._thread_poll.setInterval(400)
        self._thread_poll.timeout.connect(self._poll_backtester_thread)
        self.symbol_line.setPlaceholderText("如 600519.SSE / 000001.SZSE")
        apply_toolbar_combo_style(self.class_combo)
        apply_toolbar_combo_style(self.interval_combo)
        self._finalize_strategy_guide()
        self._apply_page_theme()

    def _create_form_controls(self) -> None:
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=3 * 365)

        self.class_combo = StrategyClassCombo()
        self.symbol_line = QtWidgets.QLineEdit(str(ASHARE_BACKTEST_DEFAULTS["vt_symbol"]))
        self.interval_combo = QtWidgets.QComboBox()
        for interval in Interval:
            self.interval_combo.addItem(interval.value)

        self.start_date_edit = QtWidgets.QDateEdit(QtCore.QDate(start_dt.year, start_dt.month, start_dt.day))
        self.end_date_edit = QtWidgets.QDateEdit(QtCore.QDate.currentDate())

        defaults = ASHARE_BACKTEST_DEFAULTS
        self.rate_line = QtWidgets.QLineEdit(format_decimal_field(defaults["rate"], places=6))
        self.slippage_line = QtWidgets.QLineEdit(format_decimal_field(defaults["slippage"], places=4))
        self.size_line = QtWidgets.QLineEdit(str(defaults["size"]))
        self.pricetick_line = QtWidgets.QLineEdit(format_decimal_field(defaults["pricetick"], places=4))
        self.capital_line = QtWidgets.QLineEdit(str(defaults["capital"]))

    def _create_action_buttons(self) -> None:
        self.run_button = QtWidgets.QPushButton("▶  开始回测")
        self.run_button.clicked.connect(self.start_backtesting)

        self.download_button = QtWidgets.QPushButton("下载数据")
        self.download_button.clicked.connect(self.start_downloading)

        self.optimization_button = QtWidgets.QPushButton("参数优化")
        self.optimization_button.clicked.connect(self.start_optimization)

        self.result_button = QtWidgets.QPushButton("优化结果")
        self.result_button.clicked.connect(self.show_optimization_result)
        self.result_button.setEnabled(False)

        self.trade_button = QtWidgets.QPushButton("成交记录")
        self.trade_button.clicked.connect(self.show_backtesting_trades)
        self.trade_button.setEnabled(False)

        self.order_button = QtWidgets.QPushButton("委托记录")
        self.order_button.clicked.connect(self.show_backtesting_orders)
        self.order_button.setEnabled(False)

        self.daily_button = QtWidgets.QPushButton("每日盈亏")
        self.daily_button.clicked.connect(self.show_daily_results)
        self.daily_button.setEnabled(False)

        self.candle_button = QtWidgets.QPushButton("K 线图表")
        self.candle_button.clicked.connect(self.show_candle_chart)
        self.candle_button.setEnabled(False)

        self.edit_button = QtWidgets.QPushButton("代码编辑")
        self.edit_button.clicked.connect(self.edit_strategy_code)

        self.reload_button = QtWidgets.QPushButton("策略重载")
        self.reload_button.clicked.connect(self.reload_strategy_class)

    def _create_result_panels(self) -> None:
        self.statistics_monitor = AshareStatisticsMonitor()
        self.log_monitor = QtWidgets.QTextEdit()
        self.chart = AshareBacktesterChart()

    def _create_dialogs(self) -> None:
        self.trade_dialog = BacktestingResultDialog(
            self.main_engine,
            self.event_engine,
            "回测成交记录",
            BacktestingTradeMonitor,
        )
        self.order_dialog = BacktestingResultDialog(
            self.main_engine,
            self.event_engine,
            "回测委托记录",
            BacktestingOrderMonitor,
        )
        self.daily_dialog = BacktestingResultDialog(
            self.main_engine,
            self.event_engine,
            "回测每日盈亏",
            DailyResultMonitor,
        )
        self.candle_dialog = CandleChartDialog()

    def _apply_page_theme(self) -> None:
        apply_vnpy_page_style(self, page_id="BacktestPage")
        style_vnpy_form_inputs(self)
        for name in (
            "symbol_line",
            "rate_line",
            "slippage_line",
            "size_line",
            "pricetick_line",
            "capital_line",
            "start_date_edit",
            "end_date_edit",
        ):
            getattr(self, name).setObjectName("BacktestInput")

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass

    def _prepare_ask_ai_button(self) -> None:
        self.ask_ai_button = QtWidgets.QPushButton("问 AI")
        self.ask_ai_button.setObjectName("SecondaryButton")
        self.ask_ai_button.setToolTip("打开 AI 助手解读最近一次回测")
        self.ask_ai_button.clicked.connect(self._ask_ai_for_backtest)

    def _prepare_strategy_guide_button(self) -> None:
        self._strategy_guide_html = ""
        self.strategy_guide_button = QtWidgets.QPushButton("说明")
        self.strategy_guide_button.setObjectName("SecondaryButton")
        self.strategy_guide_button.setToolTip("查看当前策略的适用场景与参数说明")
        self.strategy_guide_button.clicked.connect(self._show_strategy_guide_dialog)
        self.strategy_guide_button.setEnabled(False)

    def _install_strategy_guide(self, form: QtWidgets.QFormLayout) -> None:
        row_layout = QtWidgets.QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(self.class_combo, stretch=1)
        row_layout.addWidget(self.strategy_guide_button)
        container = QtWidgets.QWidget()
        container.setLayout(row_layout)
        form.addRow("交易策略", container)

    def _finalize_strategy_guide(self) -> None:
        self.class_combo.currentIndexChanged.connect(self._on_strategy_index_changed)
        self._on_strategy_index_changed(self.class_combo.currentIndex())

    def _build_strategy_guide_html(self, class_name: str) -> str:

        name = class_name.strip()
        tokens = theme_manager().tokens()
        if not name:
            colors = html_palette(tokens)
            return f'<p style="color:{colors.label};">选择策略后显示说明与适用场景。</p>'
        meta = get_strategy_meta(name)
        if meta is None:
            return str(format_missing_strategy_guide(name, tokens=tokens))
        return str(format_strategy_guide(meta, tokens=tokens))

    def _on_strategy_index_changed(self, index: int) -> None:
        del index
        class_name = self.class_combo.current_class_name()
        self._on_strategy_changed(class_name)

    def _on_strategy_changed(self, class_name: str) -> None:
        self._strategy_guide_html = self._build_strategy_guide_html(class_name)
        self.strategy_guide_button.setEnabled(bool(class_name.strip()))

    def _show_strategy_guide_dialog(self) -> None:
        class_name = self.class_combo.current_class_name()
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
            self.write_log("未发现 A 股策略，请检查项目 strategies/ 目录及策略类是否继承 AShareTemplate。")
            return

        self.class_names = ashare_names
        raw_settings = getattr(self, "settings", {})
        base_settings = dict(raw_settings) if isinstance(raw_settings, dict) else {}
        self.settings = {name: base_settings[name] for name in ashare_names if name in base_settings}
        self.class_combo.set_strategy_items(ashare_names)
        self._ensure_class_combo_selection()
        self._on_strategy_changed(self.class_combo.current_class_name())

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
        self._on_strategy_changed(self.class_combo.current_class_name())

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
        backtest_service = get_backtest_service(self.main_engine)
        if backtest_service is not None:
            return backtest_service.get_last_summary()
        return get_backtest_summary_dict()

    def _ask_ai_for_backtest(self) -> None:
        summary = self._get_last_backtest_summary()
        if not summary:
            page_notify(self, "请先完成一次回测")
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

    def _backtest_lock_widgets(self) -> list[QtWidgets.QWidget]:
        widgets: list[QtWidgets.QWidget] = [
            self.run_button,
            self.download_button,
            self.optimization_button,
            self.class_combo,
            self.symbol_line,
            self.interval_combo,
            self.start_date_edit,
            self.end_date_edit,
            self.rate_line,
            self.slippage_line,
            self.size_line,
            self.pricetick_line,
            self.capital_line,
            self.trade_button,
            self.order_button,
            self.daily_button,
            self.candle_button,
            self.edit_button,
            self.reload_button,
            self.result_button,
            self.strategy_guide_button,
            self.ask_ai_button,
        ]
        return widgets

    def _engine_busy(self) -> bool:
        thread = self.backtester_engine.thread
        return thread is not None and thread.is_alive()

    def _begin_backtest_task(self, kind: str, message: str) -> None:
        if self._task_guard.active:
            return
        self._backtest_task_kind = kind
        self._task_guard.begin(message, widgets=self._backtest_lock_widgets(), on_cancel=None)
        self._thread_poll.start()

    def _end_backtest_task_if_active(self) -> None:
        if not self._task_guard.active:
            return
        self._thread_poll.stop()
        self._task_guard.end()
        self._backtest_task_kind = None

    def _poll_backtester_thread(self) -> None:
        if not self._task_guard.active:
            self._thread_poll.stop()
            return
        if self._engine_busy():
            return
        kind = self._backtest_task_kind
        if kind == "download":
            self._end_backtest_task_if_active()
            self._toast.success("历史数据下载完成")
            return
        if kind in ("backtest", "optimization"):
            QtCore.QTimer.singleShot(120, self, self._finish_backtest_task_if_still_active)

    def _finish_backtest_task_if_still_active(self) -> None:
        if not self._task_guard.active or self._engine_busy():
            return
        self._end_backtest_task_if_active()

    def start_backtesting(self) -> None:
        if self._task_guard.active or self._engine_busy():
            page_notify(self, "已有任务在运行中，请等待完成", level="warning")
            return
        super().start_backtesting()
        if self._engine_busy():
            self._begin_backtest_task("backtest", "正在回测…")

    def start_downloading(self) -> None:
        if self._task_guard.active or self._engine_busy():
            page_notify(self, "已有任务在运行中，请等待完成", level="warning")
            return
        super().start_downloading()
        if self._engine_busy():
            self._begin_backtest_task("download", "正在下载历史数据…")

    def start_optimization(self) -> None:
        if self._task_guard.active or self._engine_busy():
            page_notify(self, "已有任务在运行中，请等待完成", level="warning")
            return
        super().start_optimization()
        if self._engine_busy():
            self._begin_backtest_task("optimization", "正在参数优化…")

    def edit_strategy_code(self) -> None:

        class_name = self.class_combo.current_class_name()
        if not class_name:
            return

        file_path = self.backtester_engine.get_strategy_class_file(class_name)
        editor_cmds = ["code", "cursor", "pycharm64", "charm"]
        editor_cmd = next((cmd for cmd in editor_cmds if shutil.which(cmd)), "")
        if editor_cmd:
            if platform.system() == "Windows":
                subprocess.run([editor_cmd, file_path], shell=True)
            else:
                subprocess.run([editor_cmd, file_path])
            return
        page_notify(
            self,
            "未检测到可用的代码编辑器，请安装 Cursor、VS Code 或 PyCharm 并加入 PATH",
            level="warning",
        )

    def process_backtesting_finished_event(self, event: Event) -> None:
        super().process_backtesting_finished_event(event)
        if self._backtest_task_kind == "backtest":
            self._end_backtest_task_if_active()
            self._toast.success("回测完成")
        statistics = self.backtester_engine.get_result_statistics()
        if not statistics:
            return
        start = cast(QtCore.QDateTime, self.start_date_edit.dateTime()).toPython()
        end = cast(QtCore.QDateTime, self.end_date_edit.dateTime()).toPython()
        start_dt = cast(datetime, start)
        end_dt = cast(datetime, end)
        summary = BacktestSummary(
            strategy=self.class_combo.current_display_title(),
            vt_symbol=self.symbol_line.text().strip(),
            interval=self.interval_combo.currentText(),
            start=start_dt.strftime("%Y-%m-%d"),
            end=end_dt.strftime("%Y-%m-%d"),
            statistics=dict(statistics),
        )
        summary_dict = summary.to_dict()
        self._write_backtest_summary_log(summary_dict)
        backtest_service = get_backtest_service(self.main_engine)
        if backtest_service is not None:
            backtest_service.persist_summary(summary_dict, source="single")
        else:
            page_notify(self, "回测服务未就绪，摘要未写入 AI 上下文", level="warning", title="回测")

    def process_optimization_finished_event(self, event: Event) -> None:
        super().process_optimization_finished_event(event)
        if self._backtest_task_kind == "optimization":
            self._end_backtest_task_if_active()
            self._toast.success("参数优化完成")
