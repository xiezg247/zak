"""系统配置 — AI 助手 Tab。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_llm.config.nl_screening_prefs import (
    load_nl_screening_confirm_enabled,
    save_nl_screening_confirm_enabled,
)

if TYPE_CHECKING:
    from vnpy_ashare.ui.shell.settings.dialog import SettingsDialog


class AiSettingsSection(QtWidgets.QWidget):
    """AI 助手行为偏好（QSettings 即时生效）。"""

    def __init__(self, dialog: SettingsDialog) -> None:
        super().__init__(dialog)
        self._dialog = dialog
        self._nl_screening_confirm = QtWidgets.QCheckBox("NL 选股执行前确认")
        self._nl_screening_confirm.setObjectName("SettingsCheck")
        self._nl_screening_confirm.setToolTip(
            "开启（默认）：AI 调用 propose_screening / propose_recipe 解析选股前弹出确认框。\n关闭：解析通过后直接执行，不再弹窗。"
        )
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(body)
        root.setContentsMargins(4, 8, 4, 8)
        root.setSpacing(12)

        hint = QtWidgets.QLabel("控制 AI 助手在终端内的交互行为。保存后立即生效；大模型 API 密钥仍在「常规」Tab 的 .env 中配置。")
        hint.setObjectName("SettingsHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        screening_group = QtWidgets.QGroupBox("选股")
        screening_group.setObjectName("SettingsGroup")
        screening_layout = QtWidgets.QVBoxLayout(screening_group)
        screening_layout.addWidget(self._nl_screening_confirm)
        screening_hint = QtWidgets.QLabel("仅影响 propose_screening / propose_recipe；run_recipe、screen_by_condition 等明确工具不受影响。")
        screening_hint.setObjectName("SettingsMeta")
        screening_hint.setWordWrap(True)
        screening_layout.addWidget(screening_hint)
        root.addWidget(screening_group)

        root.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll)

    def refresh(self) -> None:
        self._nl_screening_confirm.setChecked(load_nl_screening_confirm_enabled())

    def save_prefs(self) -> bool:
        enabled = self._nl_screening_confirm.isChecked()
        previous = load_nl_screening_confirm_enabled()
        if enabled == previous:
            return False
        save_nl_screening_confirm_enabled(enabled)
        return True
