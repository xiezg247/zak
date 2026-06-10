"""定时任务表格控件（页与对话框共用）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.market_hours import is_ashare_trading_session
from vnpy_ashare.scheduler import JobStatus, TaskSchedulerManager
from vnpy_ashare.scheduler.config import AutoScreenJobConfig, JobConfig
from vnpy_ashare.screener.recipe import list_recipe_catalog
from vnpy_ashare.ui.quotes.quotes_config import SCHEDULER_UI_FALLBACK_REFRESH_MS
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.theme.build_extra import build_scheduler_table_stylesheet


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

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
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


class _AutoScreenSettingsDialog(QtWidgets.QDialog):
    def __init__(
        self,
        job_id: str,
        status: JobStatus,
        config: AutoScreenJobConfig,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.job_id = job_id
        self.setWindowTitle(f"调度设置 - {status.name}")
        self.setMinimumWidth(400)

        form = QtWidgets.QFormLayout(self)
        trigger_kind = "intraday" if job_id == "screen_intraday" else "post_close"

        self.recipe_combo = QtWidgets.QComboBox()
        self._recipe_ids: list[str] = []
        selected_index = 0
        for index, entry in enumerate(list_recipe_catalog(trigger_kind=trigger_kind)):
            self.recipe_combo.addItem(entry.display_name)
            self._recipe_ids.append(entry.recipe_id)
            if entry.recipe_id == (config.recipe_id or ""):
                selected_index = index
        if self._recipe_ids:
            self.recipe_combo.setCurrentIndex(selected_index)
        form.addRow("引用配方", self.recipe_combo)

        self.day_edit = QtWidgets.QLineEdit(config.cron_day_of_week)
        form.addRow("星期 (cron)", self.day_edit)

        if job_id == "screen_intraday":
            self.hours_edit = QtWidgets.QLineEdit(config.cron_hours)
            form.addRow("小时 (逗号分隔)", self.hours_edit)
            self.minute_spin = QtWidgets.QSpinBox()
            self.minute_spin.setRange(0, 59)
            self.minute_spin.setValue(config.cron_minute_intraday)
            form.addRow("分钟", self.minute_spin)
        else:
            self.hour_spin = QtWidgets.QSpinBox()
            self.hour_spin.setRange(0, 23)
            self.hour_spin.setValue(config.cron_hour)
            form.addRow("小时", self.hour_spin)
            self.minute_spin = QtWidgets.QSpinBox()
            self.minute_spin.setRange(0, 59)
            self.minute_spin.setValue(config.cron_minute)
            form.addRow("分钟", self.minute_spin)

        hint = QtWidgets.QLabel("Top N 与因子权重请在「选股」页配方区配置。")
        hint.setWordWrap(True)
        form.addRow(hint)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict:
        index = self.recipe_combo.currentIndex()
        recipe_id = self._recipe_ids[index] if 0 <= index < len(self._recipe_ids) else ""
        values = {
            "recipe_id": recipe_id,
            "cron_day_of_week": self.day_edit.text().strip(),
        }
        if self.job_id == "screen_intraday":
            values["cron_hours"] = self.hours_edit.text().strip()
            values["cron_minute_intraday"] = self.minute_spin.value()
        else:
            values["cron_hour"] = self.hour_spin.value()
            values["cron_minute"] = self.minute_spin.value()
        return values


class SchedulerJobsWidget(QtWidgets.QWidget):
    """定时任务列表：启停、立即执行、调度参数。"""

    def __init__(
        self,
        scheduler: TaskSchedulerManager | None = None,
        parent: QtWidgets.QWidget | None = None,
        *,
        embedded: bool = False,
    ) -> None:
        super().__init__(parent)
        self._scheduler = scheduler
        self._embedded = embedded
        self._refreshing = False
        self._refresh_pending = False
        self._monitoring = False
        self._on_scheduler_event = self._request_refresh

        self.table = QtWidgets.QTableWidget(0, 7)
        self.table.setObjectName("SchedulerTable")
        self.table.setHorizontalHeaderLabels(["启用", "任务", "调度", "状态", "上次执行", "下次执行", "操作"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(not embedded)
        self.table.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight if embedded else QtCore.Qt.TextElideMode.ElideNone)
        self.table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setMinimumSectionSize(36)
        if embedded:
            self.table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.table.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
        self._configure_table_columns()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.table)

        if not embedded:
            refresh_button = QtWidgets.QPushButton("刷新")
            refresh_button.clicked.connect(self.refresh_table)
            button_row = QtWidgets.QHBoxLayout()
            button_row.addStretch()
            button_row.addWidget(refresh_button)
            layout.addSpacing(8)
            layout.addLayout(button_row)

        self._fallback_timer = QtCore.QTimer(self)
        self._fallback_timer.setInterval(SCHEDULER_UI_FALLBACK_REFRESH_MS)
        self._fallback_timer.timeout.connect(self.refresh_table)

        theme_manager().bind_stylesheet(self, extra=build_scheduler_table_stylesheet)
        if embedded:
            self.table.setStyleSheet("QTableWidget#SchedulerTable { border: none; background-color: transparent; }")

    def set_scheduler(self, scheduler: TaskSchedulerManager | None) -> None:
        if self._monitoring and self._scheduler is not None:
            self._scheduler.remove_listener(self._on_scheduler_event)
            self._fallback_timer.stop()
            self._monitoring = False
        self._scheduler = scheduler
        if scheduler is not None and self.isVisible():
            self.start_monitoring()

    def start_monitoring(self) -> None:
        if self._scheduler is None or self._monitoring:
            return
        self._scheduler.add_listener(self._on_scheduler_event)
        self._fallback_timer.start()
        self._monitoring = True
        self.refresh_table()

    def stop_monitoring(self) -> None:
        if not self._monitoring or self._scheduler is None:
            return
        self._scheduler.remove_listener(self._on_scheduler_event)
        self._fallback_timer.stop()
        self._monitoring = False

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._scheduler is not None:
            self.start_monitoring()

    def hideEvent(self, event) -> None:
        self.stop_monitoring()
        super().hideEvent(event)

    def _configure_table_columns(self) -> None:
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(40)

        if self._embedded:
            column_modes = {
                0: QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
                1: QtWidgets.QHeaderView.ResizeMode.Fixed,
                2: QtWidgets.QHeaderView.ResizeMode.Stretch,
                3: QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
                4: QtWidgets.QHeaderView.ResizeMode.Fixed,
                5: QtWidgets.QHeaderView.ResizeMode.Fixed,
                6: QtWidgets.QHeaderView.ResizeMode.Fixed,
            }
            for column, mode in column_modes.items():
                header.setSectionResizeMode(column, mode)
            self._apply_embedded_column_widths()
            return

        fixed_columns = (0, 1, 3, 6)
        content_columns = (2, 4, 5)
        for column in fixed_columns:
            header.setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        for column in content_columns:
            header.setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeMode.Interactive)

        self.table.setColumnWidth(1, 108)
        self.table.setColumnWidth(2, 320)
        self.table.setColumnWidth(4, 158)
        self.table.setColumnWidth(5, 158)

    def _apply_embedded_column_widths(self) -> None:
        self.table.setColumnWidth(1, 108)
        self.table.setColumnWidth(4, 148)
        self.table.setColumnWidth(5, 148)
        self.table.setColumnWidth(6, 196)

    def _sync_table_height(self) -> None:
        if not self._embedded:
            return
        row_count = self.table.rowCount()
        row_height = 0
        for row in range(row_count):
            row_height += self.table.rowHeight(row)
        if row_count == 0:
            row_height = self.table.verticalHeader().defaultSectionSize()
        frame = self.table.frameWidth() * 2
        total = self.table.horizontalHeader().height() + row_height + frame + 2
        self.table.setFixedHeight(total)
        self.setFixedHeight(total)

    def _request_refresh(self, _job_id: str) -> None:
        QtCore.QTimer.singleShot(0, self, self._request_refresh_slot)

    def _request_refresh_slot(self) -> None:
        if self._refreshing:
            self._refresh_pending = True
            return
        self.refresh_table()

    def refresh_table(self) -> None:
        if self._scheduler is None:
            return
        if self._refreshing:
            self._refresh_pending = True
            return

        self._refreshing = True
        try:
            statuses = self._scheduler.list_status()
            if self.table.rowCount() != len(statuses):
                self.table.setRowCount(len(statuses))

            for row, status in enumerate(statuses):
                self._update_row(row, status)
            self.table.resizeRowsToContents()
            if self._embedded:
                self._apply_embedded_column_widths()
            self._sync_table_height()
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
        enabled_box.toggled.connect(lambda checked, bound_job_id=job_id: self._toggle_job(bound_job_id, checked))
        self.table.setCellWidget(row, 0, enabled_box)
        return enabled_box

    def _ensure_action_widget(self, row: int, job_id: str) -> None:
        existing = self.table.cellWidget(row, 6)
        if existing is not None:
            run_button = existing.findChild(QtWidgets.QPushButton, "ActionButton")
            settings_button = existing.findChild(QtWidgets.QPushButton, "SecondaryButton")
            if run_button is not None:
                run_button.setMinimumWidth(92)
            if settings_button is not None:
                settings_button.setMinimumWidth(52)
            return

        action_widget = QtWidgets.QWidget()
        action_layout = QtWidgets.QHBoxLayout(action_widget)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(6)

        run_button = QtWidgets.QPushButton("▶ 立即执行")
        run_button.setObjectName("ActionButton")
        run_button.setMinimumWidth(92)
        run_button.clicked.connect(lambda _checked=False, bound_job_id=job_id: self._run_now(bound_job_id))

        settings_button = QtWidgets.QPushButton("设置")
        settings_button.setObjectName("SecondaryButton")
        settings_button.setMinimumWidth(52)
        settings_button.clicked.connect(lambda _checked=False, bound_job_id=job_id: self._open_settings(bound_job_id))

        action_layout.addWidget(run_button)
        action_layout.addWidget(settings_button)
        self.table.setCellWidget(row, 6, action_widget)

    def _update_row(self, row: int, status: JobStatus) -> None:
        enabled_box = self._ensure_enabled_checkbox(row, status.job_id)
        if enabled_box.isChecked() != status.enabled:
            enabled_box.blockSignals(True)
            enabled_box.setChecked(status.enabled)
            enabled_box.blockSignals(False)

        self._set_table_text(row, 1, status.name, show_tooltip=True)
        self._set_table_text(row, 2, status.schedule_text, show_tooltip=True)

        if status.running:
            state_text = "运行中"
        elif status.enabled and status.job_id == "collect_quotes" and not is_ashare_trading_session():
            state_text = "休眠中"
        elif status.enabled:
            state_text = "已启用"
        else:
            state_text = "已停止"
        self._set_table_text(row, 3, state_text)
        self._set_table_text(row, 4, status.last_run_at or "—", show_tooltip=True)
        self._set_table_text(row, 5, status.next_run_at or "—", show_tooltip=True)
        self._ensure_action_widget(row, status.job_id)

    def _toggle_job(self, job_id: str, enabled: bool) -> None:
        if self._scheduler is None:
            return
        status = self._scheduler.get_status(job_id)
        if status is not None and status.enabled == enabled:
            return
        self._scheduler.set_enabled(job_id, enabled)

    def _run_now(self, job_id: str) -> None:
        if self._scheduler is None:
            return
        if not self._scheduler.run_now(job_id):
            page_notify(self, "任务正在运行中，请稍后再试")

    def _open_settings(self, job_id: str) -> None:
        if self._scheduler is None:
            return
        status = self._scheduler.get_status(job_id)
        if not status:
            return
        config = self._scheduler.get_job_config(job_id)
        if job_id in ("screen_intraday", "screen_post_close"):
            dialog = _AutoScreenSettingsDialog(job_id, status, config, self)
        else:
            dialog = _JobSettingsDialog(job_id, status, config, self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self._scheduler.update_job_config(job_id, **dialog.values())
        self.refresh_table()
