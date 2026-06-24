"""系统配置 — 消息通知 Tab。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.app.engine_access import get_ashare_engine
from vnpy_ashare.config.schema import ENV_NOTIFY_SPECS, ConfigFieldSpec
from vnpy_ashare.notifications.core.events import (
    DEFAULT_EVENT_SUBSCRIPTIONS,
    NOTIFY_EVENT_EMOTION_STAGE_CHANGE,
    NOTIFY_EVENT_FEED_ITEM_NEW,
    NOTIFY_EVENT_POSITION_ALERT,
    NOTIFY_EVENT_RADAR_LEADER_READY,
    NOTIFY_EVENT_SCHEDULER_JOB_FAILED,
    NOTIFY_EVENT_SCREENER_INTRADAY_DONE,
    NOTIFY_EVENT_SCREENER_POST_CLOSE_DONE,
)
from vnpy_ashare.notifications.prefs.store import load_notify_prefs, save_event_subscription, save_use_interactive_card
from vnpy_ashare.ui.shell.settings.snapshot import resolve_env_config
from vnpy_common.ui.feedback import page_notify

if TYPE_CHECKING:
    from vnpy_ashare.ui.shell.settings.dialog import SettingsDialog

_EVENT_LABELS: dict[str, str] = {
    NOTIFY_EVENT_SCREENER_INTRADAY_DONE: "盘中选股完成",
    NOTIFY_EVENT_SCREENER_POST_CLOSE_DONE: "盘后选股完成",
    NOTIFY_EVENT_SCHEDULER_JOB_FAILED: "定时任务失败",
    NOTIFY_EVENT_EMOTION_STAGE_CHANGE: "情绪阶段变更",
    NOTIFY_EVENT_POSITION_ALERT: "持仓异动提醒",
    NOTIFY_EVENT_RADAR_LEADER_READY: "龙头池更新",
    NOTIFY_EVENT_FEED_ITEM_NEW: "B站 UP 更新",
}

_CONNECTION_KEYS = frozenset(
    {
        "NOTIFY_ENABLED",
        "FEISHU_WEBHOOK_URL",
        "FEISHU_WEBHOOK_SECRET",
        "NOTIFY_MIN_INTERVAL_SEC",
    },
)
_CARD_ENV_KEYS = frozenset({"NOTIFY_FEISHU_INTERACTIVE", "NOTIFY_OPEN_URL"})


class NotifySettingsSection(QtWidgets.QWidget):
    """飞书 Webhook 与事件订阅。"""

    def __init__(self, dialog: SettingsDialog) -> None:
        super().__init__(dialog)
        self._dialog = dialog
        self._event_checks: dict[str, QtWidgets.QCheckBox] = {}
        self._last_error_label = QtWidgets.QLabel("")
        self._last_error_label.setObjectName("SettingsMeta")
        self._last_error_label.setWordWrap(True)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QtWidgets.QScrollArea()
        scroll.setObjectName("SettingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QtWidgets.QWidget()
        body.setObjectName("SettingsScrollBody")
        root = QtWidgets.QVBoxLayout(body)
        root.setContentsMargins(4, 8, 4, 8)
        root.setSpacing(12)

        hint = QtWidgets.QLabel("通过飞书群自定义机器人 Webhook 推送任务提醒（不含买卖建议）。Webhook URL 仅存于本机 .env，请勿分享或提交版本库。")
        hint.setObjectName("SettingsHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        connection_specs = [spec for spec in ENV_NOTIFY_SPECS if spec.key in _CONNECTION_KEYS]
        card_env_specs = [spec for spec in ENV_NOTIFY_SPECS if spec.key in _CARD_ENV_KEYS]
        root.addWidget(self._build_env_form_group("连接", connection_specs))
        root.addWidget(self._build_events_group())
        root.addWidget(self._build_card_group(card_env_specs))

        test_row = QtWidgets.QHBoxLayout()
        test_button = QtWidgets.QPushButton("发送飞书测试消息")
        test_button.setObjectName("SettingsSecondaryButton")
        test_button.clicked.connect(self._on_test_clicked)
        test_row.addWidget(test_button)
        test_row.addStretch()
        root.addLayout(test_row)
        root.addWidget(self._last_error_label)
        root.addStretch()

        scroll.setWidget(body)
        outer.addWidget(scroll)

    def _build_env_form_group(self, title: str, specs: list[ConfigFieldSpec]) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox(title)
        group.setObjectName("SettingsGroup")
        outer = QtWidgets.QVBoxLayout(group)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        host = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(host)
        form.setContentsMargins(0, 0, 0, 0)
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        for spec in specs:
            widget = self._create_widget(spec)
            self._dialog._env_widgets[spec.key] = widget
            label = QtWidgets.QLabel(spec.label)
            label.setObjectName("SettingsFormLabel")
            if spec.description:
                label.setToolTip(spec.description)
            form.addRow(label, widget)

        outer.addWidget(host)
        return group

    def _build_events_group(self) -> QtWidgets.QGroupBox:
        events_group = QtWidgets.QGroupBox("事件订阅")
        events_group.setObjectName("SettingsGroup")
        events_layout = QtWidgets.QVBoxLayout(events_group)
        events_layout.setSpacing(6)
        for event_id, default in DEFAULT_EVENT_SUBSCRIPTIONS.items():
            check = QtWidgets.QCheckBox(_EVENT_LABELS.get(event_id, event_id))
            check.setObjectName("SettingsCheck")
            check.setChecked(default)
            self._event_checks[event_id] = check
            events_layout.addWidget(check)
        return events_group

    def _build_card_group(self, env_specs: list[ConfigFieldSpec]) -> QtWidgets.QGroupBox:
        card_group = QtWidgets.QGroupBox("飞书卡片")
        card_group.setObjectName("SettingsGroup")
        card_layout = QtWidgets.QVBoxLayout(card_group)
        card_layout.setSpacing(10)

        if env_specs:
            host = QtWidgets.QWidget()
            form = QtWidgets.QFormLayout(host)
            form.setContentsMargins(0, 0, 0, 0)
            form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
            form.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
            form.setHorizontalSpacing(12)
            form.setVerticalSpacing(10)
            form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
            for spec in env_specs:
                widget = self._create_widget(spec)
                self._dialog._env_widgets[spec.key] = widget
                label = QtWidgets.QLabel(spec.label)
                label.setObjectName("SettingsFormLabel")
                if spec.description:
                    label.setToolTip(spec.description)
                form.addRow(label, widget)
            card_layout.addWidget(host)

        self._interactive_check = QtWidgets.QCheckBox("使用 interactive 卡片（替代纯文本）")
        self._interactive_check.setObjectName("SettingsCheck")
        self._interactive_check.setToolTip("配置 NOTIFY_OPEN_URL 后卡片底部显示「打开 zak」按钮")
        card_layout.addWidget(self._interactive_check)
        return card_group

    def _create_widget(self, spec: ConfigFieldSpec) -> QtWidgets.QWidget:
        if spec.kind == "bool":
            check = QtWidgets.QCheckBox()
            check.setObjectName("SettingsCheck")
            return check
        if spec.kind == "int":
            spin = QtWidgets.QSpinBox()
            spin.setObjectName("SettingsInput")
            spin.setRange(10, 300)
            return spin
        edit = QtWidgets.QLineEdit()
        edit.setObjectName("SettingsInput")
        return edit

    def refresh(self) -> None:
        hide = self._dialog._hide_secrets.isChecked()
        env_items = {item.spec.key: item for item in resolve_env_config()}
        for spec in ENV_NOTIFY_SPECS:
            widget = self._dialog._env_widgets.get(spec.key)
            if widget is None:
                continue
            item = env_items.get(spec.key)
            value = item.value if item is not None else spec.default
            self._dialog._apply_widget_value(widget, spec, value, hide=hide)

        prefs = load_notify_prefs()
        for event_id, check in self._event_checks.items():
            check.setChecked(prefs.event_subscriptions.get(event_id, False))
        self._interactive_check.setChecked(prefs.use_interactive_card)

        service = self._notification_service()
        if service is not None and service.last_error:
            self._last_error_label.setText(f"最近发送失败：{service.last_error}")
        else:
            self._last_error_label.setText("")

    def save_subscriptions(self) -> None:
        for event_id, check in self._event_checks.items():
            save_event_subscription(event_id, check.isChecked())
        save_use_interactive_card(self._interactive_check.isChecked())

    def _notification_service(self):
        parent = self._dialog.parent()
        main_engine = getattr(parent, "main_engine", None) if parent is not None else None
        if main_engine is None:
            return None
        engine = get_ashare_engine(main_engine)
        if engine is None:
            return None
        return engine.notification_service

    def _on_test_clicked(self) -> None:
        service = self._notification_service()
        if service is None:
            page_notify(self._dialog, "Ashare 引擎未就绪", level="warning")
            return
        service.reload()
        result = service.test_send()
        if result.success:
            page_notify(self._dialog, "飞书测试消息已发送", level="success")
            self._last_error_label.setText("")
        else:
            page_notify(self._dialog, result.message, level="warning")
            self._last_error_label.setText(f"最近发送失败：{result.message}")
