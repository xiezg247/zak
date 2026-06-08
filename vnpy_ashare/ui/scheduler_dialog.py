"""定时任务管理对话框。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.scheduler import JobStatus, TaskSchedulerManager
from vnpy_ashare.scheduler.config import JobConfig
from vnpy_ashare.ui.styles import SCHEDULER_TABLE_STYLESHEET, TERMINAL_STYLESHEET


class _JobSettingsDialog(QtWidgets.QDialog):
    def __init__(
        self,
        job_id: str,
        status: JobStatus,
        config: JobConfig,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.job_id = job_id
        self.setWindowTitle(f"调度设置 - {status.name}")
        self.setMinimumWidth(360)

        form = QtWidgets.QFormLayout(self)

        if job_id == "collect_quotes":
            self.interval_spin = QtWidgets.QSpinBox()
            self.interval_spin.setRange(5, 3600)
            self.interval_spin.setValue(config.interval_seconds)
            self.interval_spin.setSuffix(" 秒")
            form.addRow("采集间隔", self.interval_spin)
        else:
            self.day_edit = QtWidgets.QLineEdit(config.cron_day_of_week)
            form.addRow("星期 (cron)", self.day_edit)

            self.hour_spin = QtWidgets.QSpinBox()
            self.hour_spin.setRange(0, 23)
            self.hour_spin.setValue(config.cron_hour)
            form.addRow("小时", self.hour_spin)

            self.minute_spin = QtWidgets.QSpinBox()
            self.minute_spin.setRange(0, 59)
            self.minute_spin.setValue(config.cron_minute)
            form.addRow("分钟", self.minute_spin)

            if job_id == "batch_download":
                self.start_edit = QtWidgets.QLineEdit(config.download_start)
                form.addRow("K 线起始日", self.start_edit)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict:
        if self.job_id == "collect_quotes":
            return {"interval_seconds": self.interval_spin.value()}
        values = {
            "cron_day_of_week": self.day_edit.text().strip(),
            "cron_hour": self.hour_spin.value(),
            "cron_minute": self.minute_spin.value(),
        }
        if self.job_id == "batch_download":
            values["download_start"] = self.start_edit.text().strip()
        return values


class SchedulerDialog(QtWidgets.QDialog):
    """定时任务列表：启停、立即执行、调度参数。"""

    def __init__(
        self,
        scheduler: TaskSchedulerManager,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.scheduler = scheduler
        self.setWindowTitle("定时任务")
        self.setMinimumSize(1020, 480)
        self.resize(1080, 520)
        self.setStyleSheet(TERMINAL_STYLESHEET + SCHEDULER_TABLE_STYLESHEET)

        hint = QtWidgets.QLabel(
            "生产环境建议独立运行 scripts/quote_collector.py；"
            "此处「行情采集」适合本机调试。"
        )
        hint.setWordWrap(True)

        self.table = QtWidgets.QTableWidget(0, 8)
        self.table.setObjectName("SchedulerTable")
        self.table.setHorizontalHeaderLabels(
            ["启用", "任务", "调度", "状态", "上次执行", "结果", "下次执行", "操作"]
        )
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setWordWrap(True)
        self.table.setTextElideMode(QtCore.Qt.TextElideMode.ElideNone)
        self.table.setHorizontalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.verticalHeader().setMinimumSectionSize(36)
        self._configure_table_columns()

        refresh_button = QtWidgets.QPushButton("刷新")
        refresh_button.clicked.connect(self.refresh_table)
        close_button = QtWidgets.QPushButton("关闭")
        close_button.clicked.connect(self.accept)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(refresh_button)
        button_row.addWidget(close_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(self.table, stretch=1)
        layout.addLayout(button_row)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self.refresh_table)

        self._refreshing = False
        self._refresh_pending = False

        self.scheduler.add_listener(self._on_scheduler_event)
        self.refresh_table()
        self._timer.start()

    def _configure_table_columns(self) -> None:
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(52)

        fixed_columns = (0, 1, 3, 7)
        content_columns = (2, 4, 5, 6)
        for column in fixed_columns:
            header.setSectionResizeMode(
                column, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
        for column in content_columns:
            header.setSectionResizeMode(
                column, QtWidgets.QHeaderView.ResizeMode.Interactive
            )

        self.table.setColumnWidth(2, 180)
        self.table.setColumnWidth(4, 158)
        self.table.setColumnWidth(5, 320)
        self.table.setColumnWidth(6, 158)

    def closeEvent(self, event) -> None:
        self.scheduler.remove_listener(self._on_scheduler_event)
        self._timer.stop()
        super().closeEvent(event)

    def _on_scheduler_event(self, _job_id: str) -> None:
        QtCore.QTimer.singleShot(0, self, self._request_refresh)

    def _request_refresh(self) -> None:
        if self._refreshing:
            self._refresh_pending = True
            return
        self.refresh_table()

    def refresh_table(self) -> None:
        if self._refreshing:
            self._refresh_pending = True
            return

        self._refreshing = True
        try:
            statuses = self.scheduler.list_status()
            if self.table.rowCount() != len(statuses):
                self.table.setRowCount(len(statuses))

            for row, status in enumerate(statuses):
                self._update_row(row, status)
            self.table.resizeRowsToContents()
        finally:
            self._refreshing = False
            if self._refresh_pending:
                self._refresh_pending = False
                QtCore.QTimer.singleShot(0, self, self.refresh_table)

    def _set_table_text(
        self,
        row: int,
        column: int,
        text: str,
        *,
        show_tooltip: bool = False,
    ) -> None:
        item = self.table.item(row, column)
        if item is None:
            item = QtWidgets.QTableWidgetItem(text)
            self.table.setItem(row, column, item)
        elif item.text() != text:
            item.setText(text)

        if show_tooltip and text and text != "—":
            item.setToolTip(text)
        else:
            item.setToolTip("")

    def _ensure_enabled_checkbox(self, row: int, job_id: str) -> QtWidgets.QCheckBox:
        widget = self.table.cellWidget(row, 0)
        if isinstance(widget, QtWidgets.QCheckBox):
            return widget

        enabled_box = QtWidgets.QCheckBox()
        enabled_box.toggled.connect(
            lambda checked, bound_job_id=job_id: self._toggle_job(bound_job_id, checked)
        )
        self.table.setCellWidget(row, 0, enabled_box)
        return enabled_box

    def _ensure_action_widget(self, row: int, job_id: str) -> None:
        if self.table.cellWidget(row, 7) is not None:
            return

        action_widget = QtWidgets.QWidget()
        action_layout = QtWidgets.QHBoxLayout(action_widget)
        action_layout.setContentsMargins(2, 2, 2, 2)
        action_layout.setSpacing(6)

        run_button = QtWidgets.QPushButton("▶ 立即执行")
        run_button.setObjectName("ActionButton")
        run_button.clicked.connect(
            lambda _checked=False, bound_job_id=job_id: self._run_now(bound_job_id)
        )

        settings_button = QtWidgets.QPushButton("设置")
        settings_button.setObjectName("SecondaryButton")
        settings_button.clicked.connect(
            lambda _checked=False, bound_job_id=job_id: self._open_settings(bound_job_id)
        )

        action_layout.addWidget(run_button)
        action_layout.addWidget(settings_button)
        self.table.setCellWidget(row, 7, action_widget)

    def _update_row(self, row: int, status: JobStatus) -> None:
        enabled_box = self._ensure_enabled_checkbox(row, status.job_id)
        if enabled_box.isChecked() != status.enabled:
            enabled_box.blockSignals(True)
            enabled_box.setChecked(status.enabled)
            enabled_box.blockSignals(False)

        self._set_table_text(row, 1, status.name)
        self._set_table_text(row, 2, status.schedule_text, show_tooltip=True)

        if status.running:
            state_text = "运行中"
        elif status.enabled:
            state_text = "已启用"
        else:
            state_text = "已停止"
        self._set_table_text(row, 3, state_text)
        self._set_table_text(
            row, 4, status.last_run_at or "—", show_tooltip=True
        )

        result_text = status.last_message or "—"
        result_item = self.table.item(row, 5)
        if result_item is None:
            result_item = QtWidgets.QTableWidgetItem(result_text)
            self.table.setItem(row, 5, result_item)
        elif result_item.text() != result_text:
            result_item.setText(result_text)

        if status.last_success is True:
            result_item.setForeground(QtCore.Qt.GlobalColor.green)
        elif status.last_success is False:
            result_item.setForeground(QtCore.Qt.GlobalColor.red)
        else:
            result_item.setForeground(self.palette().text().color())

        if result_text and result_text != "—":
            result_item.setToolTip(result_text)
        else:
            result_item.setToolTip("")

        self._set_table_text(
            row, 6, status.next_run_at or "—", show_tooltip=True
        )
        self._ensure_action_widget(row, status.job_id)

    def _toggle_job(self, job_id: str, enabled: bool) -> None:
        status = self.scheduler.get_status(job_id)
        if status is not None and status.enabled == enabled:
            return
        self.scheduler.set_enabled(job_id, enabled)

    def _run_now(self, job_id: str) -> None:
        if not self.scheduler.run_now(job_id):
            QtWidgets.QMessageBox.information(self, "提示", "任务正在运行中，请稍后再试")

    def _open_settings(self, job_id: str) -> None:
        status = self.scheduler.get_status(job_id)
        if not status:
            return
        config = self.scheduler.get_job_config(job_id)
        dialog = _JobSettingsDialog(job_id, status, config, self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self.scheduler.update_job_config(job_id, **dialog.values())
        self.refresh_table()
