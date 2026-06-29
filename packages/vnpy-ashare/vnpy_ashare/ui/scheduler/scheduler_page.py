"""定时任务页（菜单栏「后台」）。"""

from __future__ import annotations

import time

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.app.engine import APP_NAME, AshareEngine
from vnpy_ashare.scheduler.manager import TaskSchedulerManager
from vnpy_ashare.ui.quotes.page.config import SCHEDULER_UI_LOG_DEBOUNCE_MS, SCHEDULER_UI_TABLE_DEBOUNCE_MS
from vnpy_ashare.ui.scheduler.scheduler_jobs_widget import SchedulerJobsWidget
from vnpy_common.ui.feedback import PageToastHost, TaskGuard
from vnpy_common.ui.theme.build_extra import format_scheduler_empty_html, format_scheduler_run_log_html
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.tokens import ThemeTokens


class SchedulerPageWidget(QtWidgets.QWidget):
    """菜单栏「后台 → 定时任务」页。"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("MarketRoot")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self._scheduler: TaskSchedulerManager | None = None
        self._scheduler_unavailable = False
        self._log_listener = self._on_scheduler_event
        self._last_log_refresh_at = 0.0
        self._log_debounce = QtCore.QTimer(self)
        self._log_debounce.setSingleShot(True)
        self._log_debounce.setInterval(SCHEDULER_UI_LOG_DEBOUNCE_MS)
        self._log_debounce.timeout.connect(self._flush_log_refresh)
        self._table_debounce = QtCore.QTimer(self)
        self._table_debounce.setSingleShot(True)
        self._table_debounce.setInterval(SCHEDULER_UI_TABLE_DEBOUNCE_MS)
        self._build_ui()
        self._table_debounce.timeout.connect(self._jobs_widget.refresh_table)
        theme_manager().register_callback(self._on_theme_changed)

    def _on_theme_changed(self, _tokens: ThemeTokens) -> None:
        if self._scheduler is not None:
            self._refresh_logs()
        elif self._scheduler_unavailable:
            self._log_view.setHtml(format_scheduler_empty_html(theme_manager().tokens(), "A 股引擎未加载，无法管理定时任务。"))

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(12)

        title_block = QtWidgets.QVBoxLayout()
        title_block.setSpacing(4)
        title = QtWidgets.QLabel("定时任务")
        title.setObjectName("SchedulerPageTitle")
        hint = QtWidgets.QLabel(
            "生产环境建议独立运行 cli.py quotes collect；行情采集仅在 A 股交易时段（9:30–11:30、13:00–15:00）自动执行。"
            "任务由调度器在后台执行，可随时关闭本窗口，再次打开可查看进度与日志。"
        )
        hint.setObjectName("SchedulerHint")
        hint.setWordWrap(True)
        title_block.addWidget(title)
        title_block.addWidget(hint)
        header.addLayout(title_block, stretch=1)
        root.addLayout(header)

        jobs_panel = self._build_panel()
        jobs_layout = QtWidgets.QVBoxLayout(jobs_panel)
        jobs_layout.setContentsMargins(14, 12, 14, 14)
        jobs_layout.setSpacing(8)
        jobs_title = QtWidgets.QLabel("任务列表")
        jobs_title.setObjectName("SchedulerSectionLabel")
        jobs_layout.addWidget(jobs_title)
        self._jobs_widget = SchedulerJobsWidget(parent=self, embedded=True)
        jobs_layout.addWidget(self._jobs_widget, stretch=1)

        log_panel = self._build_panel()
        log_layout = QtWidgets.QVBoxLayout(log_panel)
        log_layout.setContentsMargins(14, 12, 14, 14)
        log_layout.setSpacing(8)
        self._log_title = QtWidgets.QLabel("最近执行")
        self._log_title.setObjectName("SchedulerSectionLabel")
        log_layout.addWidget(self._log_title)

        self._log_view = QtWidgets.QTextEdit()
        self._log_view.setObjectName("SchedulerLogView")
        self._log_view.setReadOnly(True)
        self._log_view.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
        self._log_view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._log_view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        log_layout.addWidget(self._log_view, stretch=1)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(jobs_panel)
        splitter.addWidget(log_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 240])
        root.addWidget(splitter, stretch=1)

        self._toast = PageToastHost(self)
        self._task_guard = TaskGuard(self._toast)
        root.addWidget(self._toast)

    @staticmethod
    def _build_panel() -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        panel.setObjectName("SchedulerPanel")
        return panel

    def _resolve_scheduler(self) -> TaskSchedulerManager | None:
        engine = self.main_engine.get_engine(APP_NAME)
        if isinstance(engine, AshareEngine):
            return engine.scheduler
        return None

    def activate(self) -> None:
        scheduler = self._resolve_scheduler()
        self._scheduler = scheduler
        self._jobs_widget.set_scheduler(scheduler)
        if scheduler is None:
            self._scheduler_unavailable = True
            self._log_view.setHtml(format_scheduler_empty_html(theme_manager().tokens(), "A 股引擎未加载，无法管理定时任务。"))
            self._log_title.setText("执行日志")
            return
        self._scheduler_unavailable = False
        scheduler.ensure_started()
        scheduler.add_listener(self._log_listener)
        self._jobs_widget.start_monitoring()
        self._refresh_all()

    def deactivate(self) -> list[str]:
        """停止 UI 监听并释放 TaskGuard；返回仍在后台运行的任务名。"""
        running: list[str] = []
        if self._scheduler is not None:
            running = [status.name for status in self._scheduler.list_status() if status.running]
        self._jobs_widget.abandon_manual_run_ui()
        self._task_guard.end()
        self._log_debounce.stop()
        self._table_debounce.stop()
        self._jobs_widget.stop_monitoring()
        if self._scheduler is not None:
            self._scheduler.remove_listener(self._log_listener)
        self._scheduler = None
        self._scheduler_unavailable = False
        return running

    def _on_scheduler_event(self, _job_id: str) -> None:
        # 调度器回调来自 APScheduler 工作线程，须切回 UI 线程再触碰 Qt 控件。
        QtCore.QTimer.singleShot(0, self, self._handle_scheduler_event)

    def _handle_scheduler_event(self) -> None:
        self._schedule_log_refresh()
        self._schedule_table_refresh()

    def _schedule_log_refresh(self) -> None:
        interval_sec = SCHEDULER_UI_LOG_DEBOUNCE_MS / 1000
        now = time.monotonic()
        if now - self._last_log_refresh_at >= interval_sec:
            self._flush_log_refresh()
            return
        if not self._log_debounce.isActive():
            self._log_debounce.start()

    def _flush_log_refresh(self) -> None:
        self._last_log_refresh_at = time.monotonic()
        self._refresh_logs()

    def _schedule_table_refresh(self) -> None:
        self._table_debounce.start()

    def _refresh_all(self) -> None:
        self._jobs_widget.refresh_table()
        self._refresh_logs()

    def _refresh_logs(self) -> None:
        if self._scheduler is None:
            return
        records = self._scheduler.list_run_log()
        if records:
            self._log_title.setText(f"最近执行 · {len(records)} 条")
        else:
            self._log_title.setText("最近执行")
        self._log_view.setHtml(format_scheduler_run_log_html(theme_manager().tokens(), records))
        scrollbar = self._log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
