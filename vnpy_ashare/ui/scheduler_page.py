"""定时任务页（左侧导航）。"""

from __future__ import annotations

import html

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.engine import APP_NAME, AshareEngine
from vnpy_ashare.scheduler import JobRunRecord, TaskSchedulerManager
from vnpy_ashare.ui.scheduler_jobs_widget import SchedulerJobsWidget
from vnpy_ashare.ui.styles import SCHEDULER_PAGE_STYLESHEET, TERMINAL_STYLESHEET


def _format_run_log_html(records: list[JobRunRecord]) -> str:
    if not records:
        return '<p style="color:#6a6a7a;margin:0;">暂无执行记录。</p>'

    lines: list[str] = []
    for record in records:
        if record.skipped:
            mark = "跳过"
            mark_color = "#8a8a8a"
        else:
            mark = "成功" if record.success else "失败"
            mark_color = "#3ddc84" if record.success else "#ff4d4f"
        message = html.escape(record.message)
        lines.append(
            "<p style='margin:0 0 6px 0;line-height:1.5;'>"
            f"<span style='color:#6a6a7a;'>{html.escape(record.finished_at)}</span> "
            f"<span style='color:#d8d8d8;'>{html.escape(record.job_name)}</span> "
            f"<span style='color:{mark_color};'>{mark}</span> "
            f"<span style='color:#989898;'>{message}</span>"
            "</p>"
        )
    return "".join(lines)


class SchedulerPageWidget(QtWidgets.QWidget):
    """左侧导航「定时任务」页。"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("MarketRoot")
        self._scheduler: TaskSchedulerManager | None = None
        self._log_listener = self._on_scheduler_event
        self._build_ui()
        self.setStyleSheet(TERMINAL_STYLESHEET + SCHEDULER_PAGE_STYLESHEET)

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
            "生产环境建议独立运行 scripts/quote_collector.py；"
            "行情采集仅在 A 股交易时段（9:30–11:30、13:00–15:00）自动执行。"
        )
        hint.setObjectName("SchedulerHint")
        hint.setWordWrap(True)
        title_block.addWidget(title)
        title_block.addWidget(hint)
        header.addLayout(title_block, stretch=1)

        self._refresh_btn = QtWidgets.QPushButton("刷新")
        self._refresh_btn.setObjectName("SecondaryButton")
        self._refresh_btn.clicked.connect(self._refresh_all)
        header.addWidget(self._refresh_btn, alignment=QtCore.Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        jobs_panel = self._build_panel()
        jobs_layout = QtWidgets.QVBoxLayout(jobs_panel)
        jobs_layout.setContentsMargins(14, 12, 14, 14)
        jobs_layout.setSpacing(8)
        jobs_title = QtWidgets.QLabel("任务列表")
        jobs_title.setObjectName("SchedulerSectionLabel")
        jobs_layout.addWidget(jobs_title)
        self._jobs_widget = SchedulerJobsWidget(parent=self, embedded=True)
        jobs_layout.addWidget(
            self._jobs_widget,
            alignment=QtCore.Qt.AlignmentFlag.AlignTop,
        )
        jobs_layout.addStretch()

        log_panel = self._build_panel()
        log_layout = QtWidgets.QVBoxLayout(log_panel)
        log_layout.setContentsMargins(14, 12, 14, 14)
        log_layout.setSpacing(8)
        self._log_title = QtWidgets.QLabel("执行日志")
        self._log_title.setObjectName("SchedulerSectionLabel")
        log_layout.addWidget(self._log_title)

        self._log_view = QtWidgets.QTextEdit()
        self._log_view.setObjectName("SchedulerLogView")
        self._log_view.setReadOnly(True)
        self._log_view.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
        self._log_view.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._log_view.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        log_layout.addWidget(self._log_view, stretch=1)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(jobs_panel)
        splitter.addWidget(log_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 480])
        root.addWidget(splitter, stretch=1)

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
            self._log_view.setHtml(
                '<p style="color:#6a6a7a;margin:0;">A 股引擎未加载，无法管理定时任务。</p>'
            )
            self._log_title.setText("执行日志")
            return
        scheduler.add_listener(self._log_listener)
        self._jobs_widget.start_monitoring()
        self._refresh_all()

    def deactivate(self) -> None:
        self._jobs_widget.stop_monitoring()
        if self._scheduler is not None:
            self._scheduler.remove_listener(self._log_listener)
        self._scheduler = None

    def _on_scheduler_event(self, _job_id: str) -> None:
        QtCore.QTimer.singleShot(0, self, self._refresh_all)

    def _refresh_all(self) -> None:
        self._jobs_widget.refresh_table()
        self._refresh_logs()

    def _refresh_logs(self) -> None:
        if self._scheduler is None:
            return
        records = self._scheduler.list_run_log()
        self._log_title.setText(
            f"执行日志 · {len(records)} 条" if records else "执行日志"
        )
        self._log_view.setHtml(_format_run_log_html(records))
        scrollbar = self._log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.minimum())
