"""A 股终端系统配置对话框。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.config_bridge import detect_config_drift, format_config_drift_summary
from vnpy_ashare.config_schema import (
    VT_DB_SPECS,
    VT_NON_DB_SPECS,
    ConfigFieldSpec,
    normalize_database_name,
)
from vnpy_ashare.paths import ENV_FILE
from vnpy_ashare.ui.fonts import (
    available_font_families,
    resolve_font_family,
    supports_font_family_selection,
)
from vnpy_ashare.ui.settings_snapshot import (
    detect_database_mode,
    env_database_name,
    format_database_status,
    mask_secret,
    resolve_env_config_database,
    resolve_env_config_general,
)
from vnpy_ashare.ui.styles import SETTINGS_DIALOG_STYLESHEET, apply_settings_combo_style
from vnpy_ashare.vt_settings import (
    SETTING_FILE,
    load_runtime_settings,
    save_runtime_settings,
    sync_vt_settings_from_env,
)


class SettingsDialog(QtWidgets.QDialog):
    """环境变量只读预览 + 运行时配置编辑。"""

    _ENV_TABLE_MAX_HEIGHT = 280
    _ENV_ROW_HEIGHT = 34
    _ENV_KEY_COLUMN_WIDTH = 220

    _SQLITE_HINT = "本地 SQLite，K 线默认写入 database.db（可在下方修改运行时路径）。"
    _QUESTDB_HINT = "QuestDB 模式需在 .env 配置连接参数，并确保服务已启动。"

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsDialog")
        self.setWindowTitle("系统配置")
        self.setMinimumSize(680, 560)
        self.resize(760, 640)
        self.setStyleSheet(SETTINGS_DIALOG_STYLESHEET)

        self._widgets: dict[str, QtWidgets.QWidget] = {}
        self._db_runtime_labels: dict[str, QtWidgets.QLabel] = {}
        self._database_mode = "sqlite"
        self._effective_database_mode = "sqlite"
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(10)

        hint = QtWidgets.QLabel(
            f"环境变量请编辑 {ENV_FILE.name}；大模型项修改后可点「重载 LLM」立即生效。其余运行时配置保存至 {SETTING_FILE.name}，字体/数据库等需重启。"
        )
        hint.setObjectName("SettingsHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._drift_label = QtWidgets.QLabel("")
        self._drift_label.setObjectName("SettingsDriftWarning")
        self._drift_label.setWordWrap(True)
        self._drift_label.setVisible(False)
        root.addWidget(self._drift_label)

        self._hide_secrets = QtWidgets.QCheckBox("隐藏密钥")
        root.addWidget(self._hide_secrets)
        self._hide_secrets.toggled.connect(self.refresh)

        scroll = QtWidgets.QScrollArea()
        scroll.setObjectName("SettingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_body = QtWidgets.QWidget()
        scroll_body.setObjectName("SettingsScrollBody")
        body_layout = QtWidgets.QVBoxLayout(scroll_body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)

        env_group = QtWidgets.QGroupBox("环境变量 (.env)")
        env_group.setObjectName("SettingsGroup")
        env_layout = QtWidgets.QVBoxLayout(env_group)
        env_layout.setSpacing(8)
        self._env_path_label = QtWidgets.QLabel()
        self._env_path_label.setObjectName("SettingsMeta")
        self._env_path_label.setWordWrap(True)
        env_layout.addWidget(self._env_path_label)
        self._env_table = self._create_env_table()
        env_layout.addWidget(self._env_table)
        body_layout.addWidget(env_group)

        db_group = QtWidgets.QGroupBox("数据库")
        db_group.setObjectName("SettingsGroup")
        db_layout = QtWidgets.QVBoxLayout(db_group)
        db_layout.setSpacing(8)
        db_layout.addLayout(self._build_database_toggle_row())
        self._db_status_label = QtWidgets.QLabel()
        self._db_status_label.setObjectName("SettingsMeta")
        self._db_status_label.setWordWrap(True)
        db_layout.addWidget(self._db_status_label)
        self._db_hint_label = QtWidgets.QLabel()
        self._db_hint_label.setObjectName("SettingsMeta")
        self._db_hint_label.setWordWrap(True)
        db_layout.addWidget(self._db_hint_label)
        self._db_env_table = self._create_env_table()
        db_layout.addWidget(self._db_env_table)

        runtime_db_label = QtWidgets.QLabel("运行时")
        runtime_db_label.setObjectName("SettingsSubheading")
        db_layout.addWidget(runtime_db_label)
        self._db_runtime_stack = QtWidgets.QStackedWidget()
        self._db_runtime_stack.addWidget(self._build_sqlite_runtime_page())
        self._db_runtime_stack.addWidget(self._build_questdb_runtime_page())
        db_layout.addWidget(self._db_runtime_stack)
        body_layout.addWidget(db_group)

        runtime_group = QtWidgets.QGroupBox("运行时 (vt_setting.json)")
        runtime_group.setObjectName("SettingsGroup")
        runtime_outer = QtWidgets.QVBoxLayout(runtime_group)
        runtime_host = QtWidgets.QWidget()
        self._runtime_form = QtWidgets.QFormLayout(runtime_host)
        self._runtime_form.setContentsMargins(0, 0, 0, 0)
        self._runtime_form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self._runtime_form.setHorizontalSpacing(12)
        self._runtime_form.setVerticalSpacing(10)
        self._runtime_form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        for spec in VT_NON_DB_SPECS:
            widget = self._create_widget(spec)
            self._widgets[spec.key] = widget
            label = QtWidgets.QLabel(spec.label)
            label.setObjectName("SettingsFormLabel")
            self._runtime_form.addRow(label, widget)
        runtime_outer.addWidget(runtime_host)
        body_layout.addWidget(runtime_group)
        body_layout.addStretch()

        scroll.setWidget(scroll_body)
        root.addWidget(scroll, stretch=1)

        button_row = QtWidgets.QHBoxLayout()
        sync_button = QtWidgets.QPushButton("从 .env 同步")
        sync_button.setObjectName("SettingsSecondaryButton")
        sync_button.clicked.connect(self._sync_from_env)
        reload_llm_button = QtWidgets.QPushButton("重载 LLM")
        reload_llm_button.setObjectName("SettingsSecondaryButton")
        reload_llm_button.setToolTip("从 .env 重新读取 LLM_API_* 并应用到 AI 助手")
        reload_llm_button.clicked.connect(self._reload_llm_config)
        save_button = QtWidgets.QPushButton("保存")
        save_button.setObjectName("SettingsPrimaryButton")
        save_button.clicked.connect(self._save)
        close_button = QtWidgets.QPushButton("关闭")
        close_button.setObjectName("SettingsSecondaryButton")
        close_button.clicked.connect(self.reject)
        button_row.addWidget(sync_button)
        button_row.addWidget(reload_llm_button)
        button_row.addStretch()
        button_row.addWidget(save_button)
        button_row.addWidget(close_button)
        root.addLayout(button_row)

    def _build_database_toggle_row(self) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(0)
        self._db_sqlite_btn = QtWidgets.QPushButton("SQLite")
        self._db_sqlite_btn.setObjectName("SettingsSegmentLeft")
        self._db_sqlite_btn.setCheckable(True)
        self._db_questdb_btn = QtWidgets.QPushButton("QuestDB")
        self._db_questdb_btn.setObjectName("SettingsSegmentRight")
        self._db_questdb_btn.setCheckable(True)
        self._db_toggle_group = QtWidgets.QButtonGroup(self)
        self._db_toggle_group.setExclusive(True)
        self._db_toggle_group.addButton(self._db_sqlite_btn, 0)
        self._db_toggle_group.addButton(self._db_questdb_btn, 1)
        self._db_toggle_group.idClicked.connect(self._on_database_toggle)
        row.addWidget(self._db_sqlite_btn)
        row.addWidget(self._db_questdb_btn)
        row.addStretch()
        return row

    def _create_env_table(self) -> QtWidgets.QTableWidget:
        table = QtWidgets.QTableWidget(0, 2)
        table.setObjectName("SettingsEnvTable")
        table.setHorizontalHeaderLabels(["变量", "值"])
        table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.setShowGrid(True)
        table.setWordWrap(False)
        table.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(self._ENV_ROW_HEIGHT)
        table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, self._ENV_KEY_COLUMN_WIDTH)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setFixedHeight(self._ENV_ROW_HEIGHT)
        table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        return table

    def _build_sqlite_runtime_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(page)
        form.setContentsMargins(0, 0, 0, 0)
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self._add_runtime_field(form, "database.database", "数据库文件")
        return page

    def _build_questdb_runtime_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(page)
        form.setContentsMargins(0, 0, 0, 0)
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        for spec in VT_DB_SPECS:
            if spec.key in {"database.name", "database.database"}:
                continue
            self._add_runtime_field(form, spec.key, spec.label)
        return page

    def _add_runtime_field(
        self,
        form: QtWidgets.QFormLayout,
        key: str,
        label_text: str,
    ) -> None:
        spec = next(item for item in VT_DB_SPECS if item.key == key)
        widget = self._create_widget(spec)
        self._widgets[key] = widget
        label = QtWidgets.QLabel(label_text)
        label.setObjectName("SettingsFormLabel")
        self._db_runtime_labels[key] = label
        form.addRow(label, widget)

    def _create_widget(self, spec: ConfigFieldSpec) -> QtWidgets.QWidget:
        if spec.key == "font.family":
            return self._create_font_family_widget()
        if spec.kind == "bool":
            check = QtWidgets.QCheckBox()
            check.setObjectName("SettingsCheck")
            return check
        if spec.kind == "int":
            spin = QtWidgets.QSpinBox()
            spin.setObjectName("SettingsInput")
            spin.setRange(0, 1_000_000)
            return spin
        if spec.kind == "choice":
            combo = QtWidgets.QComboBox()
            combo.setObjectName("SettingsInput")
            combo.addItems(list(spec.choices))
            apply_settings_combo_style(combo)
            return combo
        edit = QtWidgets.QLineEdit()
        edit.setObjectName("SettingsInput")
        return edit

    def _create_font_family_widget(self) -> QtWidgets.QWidget:
        if supports_font_family_selection():
            combo = QtWidgets.QComboBox()
            combo.setObjectName("SettingsInput")
            combo.addItems(list(available_font_families()))
            apply_settings_combo_style(combo)
            return combo
        edit = QtWidgets.QLineEdit()
        edit.setObjectName("SettingsInput")
        edit.setReadOnly(True)
        edit.setToolTip("当前系统仅支持默认字体，不可切换")
        return edit

    def refresh(self) -> None:
        path_text = str(ENV_FILE)
        if not ENV_FILE.is_file():
            path_text += "（未找到，以下为默认值）"
        self._env_path_label.setText(path_text)

        settings = load_runtime_settings()
        self._effective_database_mode = detect_database_mode(runtime_settings=settings)
        self._set_database_mode(self._effective_database_mode, refresh_tables=False)

        self._refresh_env_table(self._env_table, resolve_env_config_general())
        self._refresh_env_table(
            self._db_env_table,
            resolve_env_config_database(self._database_mode),
        )
        self._update_database_status()
        self._populate_runtime_fields(settings)
        self._update_drift_warning(settings)

    def _update_drift_warning(self, settings: dict) -> None:
        drifts = detect_config_drift(settings)
        summary = format_config_drift_summary(drifts)
        self._drift_label.setText(summary)
        self._drift_label.setVisible(bool(summary))

    def _on_database_toggle(self, index: int) -> None:
        mode = "questdb" if index == 1 else "sqlite"
        self._set_database_mode(mode, refresh_tables=True)

    def _set_database_mode(self, mode: str, *, refresh_tables: bool) -> None:
        self._database_mode = normalize_database_name(mode)
        self._db_sqlite_btn.setChecked(self._database_mode == "sqlite")
        self._db_questdb_btn.setChecked(self._database_mode == "questdb")
        self._db_hint_label.setText(self._QUESTDB_HINT if self._database_mode == "questdb" else self._SQLITE_HINT)
        self._db_runtime_stack.setCurrentIndex(0 if self._database_mode == "sqlite" else 1)
        self._update_database_status()
        if refresh_tables:
            self._refresh_env_table(
                self._db_env_table,
                resolve_env_config_database(self._database_mode),
            )

    def _update_database_status(self) -> None:
        self._db_status_label.setText(
            format_database_status(
                effective=self._effective_database_mode,
                env_name=env_database_name(),
                editing=self._database_mode,
            )
        )

    def _refresh_env_table(
        self,
        table: QtWidgets.QTableWidget,
        items: list,
    ) -> None:
        hide = self._hide_secrets.isChecked()
        align = QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        table.setRowCount(len(items))
        for row, item in enumerate(items):
            display_value = item.value
            if hide and item.spec.sensitive and display_value:
                display_value = mask_secret(display_value)

            key_item = QtWidgets.QTableWidgetItem(item.spec.key)
            key_item.setTextAlignment(align)
            key_item.setFlags(key_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)

            value_item = QtWidgets.QTableWidgetItem(display_value)
            value_item.setTextAlignment(align)
            tooltip = item.value or item.spec.default
            if item.file_value and item.file_value != item.value:
                tooltip = f"当前模式：{item.value}\n.env 文件：{item.file_value}"
            value_item.setToolTip(tooltip)
            value_item.setFlags(value_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)

            table.setItem(row, 0, key_item)
            table.setItem(row, 1, value_item)
            table.setRowHeight(row, self._ENV_ROW_HEIGHT)

        self._fit_env_table_height(table)

    def _fit_env_table_height(self, table: QtWidgets.QTableWidget) -> None:
        row_count = table.rowCount()
        header_h = table.horizontalHeader().height()
        frame = table.frameWidth() * 2
        height = header_h + row_count * self._ENV_ROW_HEIGHT + frame + 2
        if height > self._ENV_TABLE_MAX_HEIGHT:
            table.setFixedHeight(self._ENV_TABLE_MAX_HEIGHT)
        else:
            table.setFixedHeight(max(height, 120))

    def _populate_runtime_fields(self, settings: dict) -> None:
        hide = self._hide_secrets.isChecked()
        all_specs = (*VT_NON_DB_SPECS, *VT_DB_SPECS)
        for spec in all_specs:
            widget = self._widgets.get(spec.key)
            if widget is None:
                continue
            value = settings.get(spec.key, spec.default)
            text = str(value)
            if spec.key == "font.family":
                text = resolve_font_family(text)
            if isinstance(widget, QtWidgets.QLineEdit):
                widget.setText(text)
                widget.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password if hide and spec.sensitive else QtWidgets.QLineEdit.EchoMode.Normal)
            elif isinstance(widget, QtWidgets.QSpinBox):
                try:
                    widget.setValue(int(value))
                except (TypeError, ValueError):
                    widget.setValue(int(spec.default or 0))
            elif isinstance(widget, QtWidgets.QComboBox):
                if widget.findText(text) < 0:
                    widget.addItem(text)
                widget.setCurrentText(text)
            elif isinstance(widget, QtWidgets.QCheckBox):
                widget.setChecked(str(value).lower() in {"true", "1"} or value is True)

    def _collect_updates(self) -> dict:
        updates: dict = {}
        all_specs = (*VT_NON_DB_SPECS, *VT_DB_SPECS)
        for spec in all_specs:
            widget = self._widgets.get(spec.key)
            if widget is None:
                continue
            if isinstance(widget, QtWidgets.QLineEdit):
                raw = widget.text().strip()
                if spec.kind == "bool":
                    updates[spec.key] = raw.lower() in {"true", "1", "yes"}
                elif spec.kind == "int":
                    try:
                        updates[spec.key] = int(raw)
                    except ValueError:
                        updates[spec.key] = int(spec.default or 0)
                else:
                    updates[spec.key] = raw
            elif isinstance(widget, QtWidgets.QSpinBox):
                updates[spec.key] = widget.value()
            elif isinstance(widget, QtWidgets.QComboBox):
                updates[spec.key] = widget.currentText()
            elif isinstance(widget, QtWidgets.QCheckBox):
                updates[spec.key] = widget.isChecked()
        updates["database.name"] = self._database_mode
        return updates

    def _save(self) -> None:
        path = save_runtime_settings(self._collect_updates())
        QtWidgets.QMessageBox.information(
            self,
            "已保存",
            f"配置已写入 {path}\n字体、数据库等项需重启应用后生效。",
        )
        self.accept()

    def _reload_llm_config(self) -> None:
        parent = self.parent()
        engine = None
        if parent is not None and hasattr(parent, "_get_llm_engine"):
            engine = parent._get_llm_engine()
        if engine is None:
            QtWidgets.QMessageBox.warning(self, "提示", "LLM 引擎未加载")
            return
        cfg = engine.reload_config()
        if cfg.configured:
            QtWidgets.QMessageBox.information(
                self,
                "LLM 已重载",
                f"模型：{cfg.model}\nAPI：{cfg.api_base}\nKey：{cfg.masked_key()}",
            )
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "LLM 未配置",
                "未检测到 LLM_API_KEY，请编辑 .env 后再次重载。",
            )

    def _sync_from_env(self) -> None:
        reply = QtWidgets.QMessageBox.question(
            self,
            "从 .env 同步",
            f"将用 .env 重建 {SETTING_FILE.name}，并覆盖当前运行时配置。\n是否继续？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        path = sync_vt_settings_from_env(backup=True)
        self.refresh()
        QtWidgets.QMessageBox.information(
            self,
            "同步完成",
            f"已从 .env 写入 {path}\n字体、数据库等项需重启应用后生效；大模型项可点「重载 LLM」立即应用。",
        )


def show_settings_dialog(parent: QtWidgets.QWidget | None = None) -> None:
    SettingsDialog(parent).exec()
