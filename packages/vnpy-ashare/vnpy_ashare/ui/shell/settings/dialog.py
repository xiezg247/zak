"""A 股终端系统配置对话框。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.config.apply import (
    apply_env_side_effects,
    apply_llm_reload,
    apply_runtime_settings,
    build_apply_context,
    diff_settings,
    format_combined_save_summary,
    format_env_sync_summary,
)
from vnpy_ashare.config.bridge import detect_config_drift, format_config_drift_summary, load_effective_env_values
from vnpy_ashare.config.env_store import save_env_values
from vnpy_ashare.config.fonts import (
    available_font_families,
    resolve_font_family,
    supports_font_family_selection,
)
from vnpy_ashare.config.schema import (
    ENV_GENERAL_SPECS,
    ENV_POSTGRES_KEYS,
    ENV_SPEC_BY_KEY,
    VT_DB_SPECS,
    VT_NON_DB_SPECS,
    ConfigFieldSpec,
)
from vnpy_ashare.config.vt_settings import (
    SETTING_FILE,
    load_runtime_settings,
    save_runtime_settings,
    sync_vt_settings_from_env,
)
from vnpy_ashare.ui.shell.settings.ai_section import AiSettingsSection
from vnpy_ashare.ui.shell.settings.emotion_section import EmotionSettingsSection
from vnpy_ashare.ui.shell.settings.notify_section import NotifySettingsSection
from vnpy_ashare.ui.shell.settings.snapshot import (
    collect_database_runtime_updates,
    detect_database_mode,
    env_database_name,
    format_bar_database_status,
    format_meta_storage_root,
    metadata_storage_entries,
    resolve_database_runtime_display,
    resolve_env_config,
)
from vnpy_ashare.ui.styles.vnpy_page import apply_settings_combo_style
from vnpy_common.paths import ENV_FILE
from vnpy_common.ui.feedback import confirm_action, page_notify
from vnpy_common.ui.theme.build_extra import build_settings_stylesheet
from vnpy_common.ui.theme.manager import theme_manager


class SettingsDialog(QtWidgets.QDialog):
    """环境变量 + 运行时配置编辑。"""

    _ENV_FORM_MAX_HEIGHT = 320
    _ENV_ROW_HEIGHT = 34
    _ENV_KEY_COLUMN_WIDTH = 220

    _POSTGRES_METADATA_HINT = (
        "元数据与 AI 对话写入 PostgreSQL（schema app / chat / auth / cache），"
        "由 .env 中 DATABASE_URL 或 POSTGRES_* 配置。"
    )

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsDialog")
        self.setWindowTitle("系统配置")
        self.setMinimumSize(680, 560)
        self.resize(760, 640)
        theme_manager().bind_stylesheet(self, extra=build_settings_stylesheet)

        self._widgets: dict[str, QtWidgets.QWidget] = {}
        self._env_widgets: dict[str, QtWidgets.QWidget] = {}
        self._db_runtime_labels: dict[str, QtWidgets.QLabel] = {}
        self._effective_database_mode = "postgresql"
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(10)

        hint = QtWidgets.QLabel(
            f"环境变量写入 {ENV_FILE.name}，运行时写入 {SETTING_FILE.name}；保存后按项即时生效或提示需重启。"
            f"若仅改 .env 且需覆盖 vt_setting，请点「从 .env 同步」。大模型也可点「重载 LLM」。"
            f"元数据、AI 对话与 K 线均使用 PostgreSQL（.env 中 DATABASE_URL / POSTGRES_*）。"
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
        self._env_form_scroll = self._wrap_env_form(self._build_env_general_form())
        env_layout.addWidget(self._env_form_scroll)
        body_layout.addWidget(env_group)

        body_layout.addWidget(self._build_metadata_group())

        db_group = QtWidgets.QGroupBox("K 线数据")
        db_group.setObjectName("SettingsGroup")
        db_layout = QtWidgets.QVBoxLayout(db_group)
        db_layout.setSpacing(8)
        self._db_status_label = QtWidgets.QLabel()
        self._db_status_label.setObjectName("SettingsMeta")
        self._db_status_label.setWordWrap(True)
        db_layout.addWidget(self._db_status_label)

        env_db_label = QtWidgets.QLabel(".env（可编辑；K 线库类型变更后建议「从 .env 同步」）")
        env_db_label.setObjectName("SettingsSubheading")
        db_layout.addWidget(env_db_label)
        self._env_pg_form_scroll = self._wrap_env_form(self._build_env_kline_form())
        db_layout.addWidget(self._env_pg_form_scroll)

        runtime_db_label = QtWidgets.QLabel("运行时 vt_setting.json（可编辑；K 线库变更需重启）")
        runtime_db_label.setObjectName("SettingsSubheading")
        db_layout.addWidget(runtime_db_label)
        db_layout.addWidget(self._build_kline_runtime_form())
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

        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setObjectName("SettingsTabs")
        self._tabs.addTab(scroll, "常规")
        self._notify_section = NotifySettingsSection(self)
        self._tabs.addTab(self._notify_section, "通知")
        self._ai_section = AiSettingsSection(self)
        self._tabs.addTab(self._ai_section, "AI 助手")
        self._emotion_section = EmotionSettingsSection(self)
        self._tabs.addTab(self._emotion_section, "情绪周期")
        root.addWidget(self._tabs, stretch=1)

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

    def _build_metadata_group(self) -> QtWidgets.QGroupBox:
        title = "元数据（PostgreSQL）"
        group = QtWidgets.QGroupBox(title)
        group.setObjectName("SettingsGroup")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(8)

        self._meta_hint_label = QtWidgets.QLabel()
        self._meta_hint_label.setObjectName("SettingsMeta")
        self._meta_hint_label.setWordWrap(True)
        layout.addWidget(self._meta_hint_label)

        self._meta_root_label = QtWidgets.QLabel()
        self._meta_root_label.setObjectName("SettingsMeta")
        self._meta_root_label.setWordWrap(True)
        layout.addWidget(self._meta_root_label)

        self._meta_table = self._create_env_table()
        self._meta_table.setHorizontalHeaderLabels(["配置项", "路径与说明"])
        layout.addWidget(self._meta_table)
        return group

    def _wrap_env_form(self, host: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
        scroll = QtWidgets.QScrollArea()
        scroll.setObjectName("SettingsEnvFormScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(host)
        scroll.setMaximumHeight(self._ENV_FORM_MAX_HEIGHT)
        return scroll

    def _build_env_general_form(self) -> QtWidgets.QWidget:
        host = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(host)
        form.setContentsMargins(0, 0, 0, 0)
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        for spec in ENV_GENERAL_SPECS:
            widget = self._create_widget(spec)
            self._env_widgets[spec.key] = widget
            label = QtWidgets.QLabel(spec.label)
            label.setObjectName("SettingsFormLabel")
            if spec.description:
                label.setToolTip(spec.description)
            form.addRow(label, widget)
        return host

    def _build_env_kline_form(self) -> QtWidgets.QWidget:
        host = QtWidgets.QWidget()
        pg_form = QtWidgets.QFormLayout(host)
        pg_form.setContentsMargins(0, 0, 0, 0)
        pg_form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        pg_form.setHorizontalSpacing(12)
        pg_form.setVerticalSpacing(10)
        pg_form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        db_spec = ENV_SPEC_BY_KEY["DATABASE_NAME"]
        db_widget = self._create_widget(db_spec)
        self._env_widgets["DATABASE_NAME"] = db_widget
        db_label = QtWidgets.QLabel(db_spec.label)
        db_label.setObjectName("SettingsFormLabel")
        pg_form.addRow(db_label, db_widget)
        if isinstance(db_widget, QtWidgets.QComboBox):
            db_widget.setEnabled(False)
        for key in sorted(ENV_POSTGRES_KEYS):
            spec = ENV_SPEC_BY_KEY[key]
            widget = self._create_widget(spec)
            self._env_widgets[key] = widget
            label = QtWidgets.QLabel(spec.label)
            label.setObjectName("SettingsFormLabel")
            pg_form.addRow(label, widget)
        return host

    def _build_kline_runtime_form(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(page)
        form.setContentsMargins(0, 0, 0, 0)
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        for spec in VT_DB_SPECS:
            self._add_runtime_field(form, spec.key, spec.label)
        return page

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

    def _add_runtime_field(
        self,
        form: QtWidgets.QFormLayout,
        key: str,
        label_text: str,
    ) -> None:
        spec = next(item for item in VT_DB_SPECS if item.key == key)
        widget = self._create_widget(spec)
        if key == "database.name" and isinstance(widget, QtWidgets.QComboBox):
            widget.setEnabled(False)
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

        self._populate_env_fields()
        self._populate_runtime_fields(settings)
        self._populate_database_runtime_fields(settings)
        self._update_database_status()
        self._refresh_metadata_table(settings)
        self._update_drift_warning(settings)
        self._notify_section.refresh()
        self._ai_section.refresh()
        self._emotion_section.refresh()

    def _refresh_metadata_table(self, settings: dict) -> None:
        self._meta_hint_label.setText(self._POSTGRES_METADATA_HINT)
        self._meta_root_label.setText(format_meta_storage_root())
        entries = metadata_storage_entries(settings)
        align = QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        self._meta_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            key_item = QtWidgets.QTableWidgetItem(entry.key)
            key_item.setTextAlignment(align)
            key_item.setFlags(key_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            key_item.setToolTip(entry.relative or entry.description)

            if entry.relative:
                value_text = f"{entry.relative} → {entry.path}\n{entry.description}"
            else:
                value_text = entry.description
            value_item = QtWidgets.QTableWidgetItem(value_text)
            value_item.setTextAlignment(align)
            value_item.setToolTip(value_text)
            value_item.setFlags(value_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)

            self._meta_table.setItem(row, 0, key_item)
            self._meta_table.setItem(row, 1, value_item)
            self._meta_table.setRowHeight(row, self._ENV_ROW_HEIGHT)

        self._fit_env_table_height(self._meta_table)

    def _update_database_status(self) -> None:
        self._db_status_label.setText(
            format_bar_database_status(
                effective=self._effective_database_mode,
                env_name=env_database_name(),
                pending=self._effective_database_mode,
            )
        )

    def _populate_env_fields(self) -> None:
        hide = self._hide_secrets.isChecked()
        env_items = {item.spec.key: item for item in resolve_env_config()}
        for key, widget in self._env_widgets.items():
            spec = ENV_SPEC_BY_KEY.get(key)
            if spec is None:
                continue
            item = env_items.get(key)
            value = item.value if item is not None else spec.default
            self._apply_widget_value(widget, spec, value, hide=hide)

    def _collect_env_updates(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for key, widget in self._env_widgets.items():
            spec = ENV_SPEC_BY_KEY.get(key)
            if spec is None:
                continue
            raw = self._read_widget_value(widget, spec)
            values[key] = str(raw)
        return values

    def _update_drift_warning(self, settings: dict) -> None:
        drifts = detect_config_drift(settings)
        summary = format_config_drift_summary(drifts)
        self._drift_label.setText(summary)
        self._drift_label.setVisible(bool(summary))

    def _fit_env_table_height(self, table: QtWidgets.QTableWidget) -> None:
        row_count = table.rowCount()
        header_h = table.horizontalHeader().height()
        frame = table.frameWidth() * 2
        height = header_h + row_count * self._ENV_ROW_HEIGHT + frame + 2
        if height > self._ENV_FORM_MAX_HEIGHT:
            table.setFixedHeight(self._ENV_FORM_MAX_HEIGHT)
        else:
            table.setFixedHeight(max(height, 120))

    def _populate_runtime_fields(self, settings: dict) -> None:
        hide = self._hide_secrets.isChecked()
        for spec in VT_NON_DB_SPECS:
            widget = self._widgets.get(spec.key)
            if widget is None:
                continue
            value = settings.get(spec.key, spec.default)
            self._apply_widget_value(widget, spec, value, hide=hide)

    def _populate_database_runtime_fields(self, settings: dict) -> None:
        hide = self._hide_secrets.isChecked()
        db_settings = resolve_database_runtime_display(settings)
        for spec in VT_DB_SPECS:
            widget = self._widgets.get(spec.key)
            if widget is None:
                continue
            value = db_settings.get(spec.key, spec.default)
            self._apply_widget_value(widget, spec, value, hide=hide)

    def _apply_widget_value(
        self,
        widget: QtWidgets.QWidget,
        spec: ConfigFieldSpec,
        value: object,
        *,
        hide: bool,
    ) -> None:
        text = str(value)
        if spec.key == "font.family":
            text = resolve_font_family(text)
        if isinstance(widget, QtWidgets.QLineEdit):
            widget.setText(text)
            widget.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password if hide and spec.sensitive else QtWidgets.QLineEdit.EchoMode.Normal)
        elif isinstance(widget, QtWidgets.QSpinBox):
            try:
                widget.setValue(int(str(value)))
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
        for spec in VT_NON_DB_SPECS:
            widget = self._widgets.get(spec.key)
            if widget is None:
                continue
            updates[spec.key] = self._read_widget_value(widget, spec)

        db_widget_values: dict[str, object] = {}
        for spec in VT_DB_SPECS:
            widget = self._widgets.get(spec.key)
            if widget is None:
                continue
            db_widget_values[spec.key] = self._read_widget_value(widget, spec)

        updates.update(
            collect_database_runtime_updates(db_widget_values)
        )
        return updates

    def _read_widget_value(self, widget: QtWidgets.QWidget, spec: ConfigFieldSpec) -> object:
        if isinstance(widget, QtWidgets.QLineEdit):
            raw = widget.text().strip()
            if spec.kind == "bool":
                return raw.lower() in {"true", "1", "yes"}
            if spec.kind == "int":
                try:
                    return int(raw)
                except ValueError:
                    return int(spec.default or 0)
            return raw
        if isinstance(widget, QtWidgets.QSpinBox):
            return widget.value()
        if isinstance(widget, QtWidgets.QComboBox):
            return widget.currentText()
        if isinstance(widget, QtWidgets.QCheckBox):
            return widget.isChecked()
        return spec.default

    def _save(self) -> None:
        previous_env = load_effective_env_values()
        previous_runtime = load_runtime_settings()
        env_updates = self._collect_env_updates()
        runtime_updates = self._collect_updates()
        env_changed = diff_settings(previous_env, env_updates)
        runtime_changed = diff_settings(previous_runtime, runtime_updates)

        self._notify_section.save_subscriptions()
        ai_saved = self._ai_section.save_prefs()
        emotion_saved = self._emotion_section.save_thresholds()
        ctx = build_apply_context(self)
        if ctx.notification_service is not None:
            ctx.notification_service.reload()

        if not env_changed and not runtime_changed:
            if emotion_saved:
                page_notify(self, "情绪周期阈值已保存并生效", level="success")
            elif ai_saved:
                page_notify(self, "AI 助手偏好已保存并生效", level="success")
            else:
                page_notify(self, "事件订阅已保存", level="success")
            self.refresh()
            return

        results: list = []
        env_path: str | None = None
        runtime_path: str | None = None

        if env_changed:
            env_path = str(save_env_values(env_updates))
            results.extend(apply_env_side_effects(set(env_changed.keys()), context=ctx))

        if runtime_changed:
            runtime_path = str(save_runtime_settings(runtime_updates))
            results.extend(apply_runtime_settings(runtime_changed, context=ctx))

        page_notify(
            self,
            format_combined_save_summary(
                env_path=env_path,
                runtime_path=runtime_path,
                results=results,
            ),
            level="success",
        )
        self.refresh()
        self.accept()

    def _reload_llm_config(self) -> None:
        result = apply_llm_reload(build_apply_context(self))
        page_notify(
            self,
            f"{result.label} — {result.message}",
            level="success" if result.success else "warning",
        )

    def _sync_from_env(self) -> None:
        if not confirm_action(
            self,
            "从 .env 同步",
            f"将用 .env 重建 {SETTING_FILE.name}，并覆盖当前运行时配置。\n是否继续？",
            confirm_text="同步",
        ):
            return
        previous_runtime = load_runtime_settings()
        previous_env = load_effective_env_values(ENV_FILE)
        path = sync_vt_settings_from_env(backup=True)
        new_runtime = load_runtime_settings()
        runtime_changed = diff_settings(previous_runtime, new_runtime)
        new_env = load_effective_env_values(ENV_FILE)
        env_changed_keys = {key for key in set(previous_env) | set(new_env) if previous_env.get(key) != new_env.get(key)}

        ctx = build_apply_context(self)
        results = apply_runtime_settings(runtime_changed, context=ctx)
        results.extend(apply_env_side_effects(env_changed_keys, context=ctx))

        self.refresh()
        page_notify(
            self,
            format_env_sync_summary(str(path), results),
            level="success",
        )


def show_settings_dialog(parent: QtWidgets.QWidget | None = None) -> None:
    SettingsDialog(parent).exec()
