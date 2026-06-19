"""系统配置 — 情绪周期阈值 Tab。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.config.preferences.emotion_cycle import (
    EmotionCycleThresholds,
    load_emotion_cycle_thresholds,
    reset_emotion_cycle_thresholds,
    save_emotion_cycle_thresholds,
)
from vnpy_ashare.quotes.market.emotion_cycle import invalidate_emotion_cycle_cache
from vnpy_ashare.quotes.market.emotion_cycle_hysteresis import reset_emotion_stage_hysteresis
from vnpy_common.ui.feedback import confirm_action, page_notify

if TYPE_CHECKING:
    from vnpy_ashare.ui.shell.settings.dialog import SettingsDialog


class EmotionSettingsSection(QtWidgets.QWidget):
    """情绪周期五阶段判定阈值（QSettings 即时生效）。"""

    def __init__(self, dialog: SettingsDialog) -> None:
        super().__init__(dialog)
        self._dialog = dialog
        self._spinners: dict[str, QtWidgets.QSpinBox] = {}
        self._doubles: dict[str, QtWidgets.QDoubleSpinBox] = {}
        self._hysteresis_check = QtWidgets.QCheckBox("启用阶段迟滞（减少涨停家数边界抖动）")
        self._hysteresis_check.setObjectName("SettingsInput")
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

        hint = QtWidgets.QLabel("调整情绪周期引擎的阶段判定阈值。保存后立即重算缓存；顶栏芯片与选股 gate 共用同一套规则。")
        hint.setObjectName("SettingsHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        stage_group = QtWidgets.QGroupBox("阶段判定")
        stage_group.setObjectName("SettingsGroup")
        stage_form = QtWidgets.QFormLayout(stage_group)
        stage_form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        stage_form.setHorizontalSpacing(12)
        stage_form.setVerticalSpacing(10)
        self._add_ratio_row(stage_form, "recession_break_rate", "退潮 · 断板率 ≥", 0.0, 1.0)
        self._add_int_row(stage_form, "recession_limit_down", "退潮 · 跌停 ≥", 0, 200)
        self._add_int_row(stage_form, "ice_max_boards", "冰点 · 最高连板 ≤", 0, 10)
        self._add_int_row(stage_form, "ice_limit_down", "冰点 · 跌停 ≥", 0, 100)
        self._add_ratio_row(stage_form, "ice_up_ratio_max", "冰点 · 上涨占比 <", 0.0, 1.0)
        self._add_int_row(stage_form, "climax_ladder_depth", "高潮 · 梯队层数 ≥", 0, 10)
        self._add_int_row(stage_form, "climax_limit_up", "高潮 · 涨停 ≥", 0, 300)
        self._add_int_row(stage_form, "divergence_limit_up_min", "分歧 · 涨停 ≥", 0, 200)
        self._add_int_row(stage_form, "divergence_limit_spread", "分歧 · |涨−跌| ≤", 0, 50)
        self._add_int_row(stage_form, "startup_max_boards", "启动 · 最高连板 ≥", 0, 15)
        self._add_int_row(stage_form, "startup_limit_up", "启动 · 涨停 ≥", 0, 200)
        root.addWidget(stage_group)

        aux_group = QtWidgets.QGroupBox("辅助系数")
        aux_group.setObjectName("SettingsGroup")
        aux_form = QtWidgets.QFormLayout(aux_group)
        aux_form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        aux_form.setHorizontalSpacing(12)
        aux_form.setVerticalSpacing(10)
        self._add_amount_row(aux_form, "amount_floor_yuan", "成交额降仓线（元）")
        self._add_double_row(aux_form, "fear_greed_overheat", "恐贪过热线", 0.0, 100.0, decimals=0)
        root.addWidget(aux_group)

        behavior_group = QtWidgets.QGroupBox("行为")
        behavior_group.setObjectName("SettingsGroup")
        behavior_layout = QtWidgets.QVBoxLayout(behavior_group)
        behavior_layout.addWidget(self._hysteresis_check)
        root.addWidget(behavior_group)

        button_row = QtWidgets.QHBoxLayout()
        reset_button = QtWidgets.QPushButton("恢复默认")
        reset_button.setObjectName("SettingsSecondaryButton")
        reset_button.clicked.connect(self._reset_defaults)
        button_row.addWidget(reset_button)
        button_row.addStretch()
        root.addLayout(button_row)
        root.addStretch()

        scroll.setWidget(body)
        outer.addWidget(scroll)

    def _add_int_row(self, form: QtWidgets.QFormLayout, field: str, label: str, min_v: int, max_v: int) -> None:
        spin = QtWidgets.QSpinBox()
        spin.setObjectName("SettingsInput")
        spin.setRange(min_v, max_v)
        self._spinners[field] = spin
        row_label = QtWidgets.QLabel(label)
        row_label.setObjectName("SettingsFormLabel")
        form.addRow(row_label, spin)

    def _add_ratio_row(self, form: QtWidgets.QFormLayout, field: str, label: str, min_v: float, max_v: float) -> None:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setObjectName("SettingsInput")
        spin.setRange(min_v, max_v)
        spin.setDecimals(2)
        spin.setSingleStep(0.01)
        self._doubles[field] = spin
        row_label = QtWidgets.QLabel(label)
        row_label.setObjectName("SettingsFormLabel")
        form.addRow(row_label, spin)

    def _add_amount_row(self, form: QtWidgets.QFormLayout, field: str, label: str) -> None:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setObjectName("SettingsInput")
        spin.setRange(0.0, 1e14)
        spin.setDecimals(0)
        spin.setSingleStep(1e11)
        self._doubles[field] = spin
        row_label = QtWidgets.QLabel(label)
        row_label.setObjectName("SettingsFormLabel")
        form.addRow(row_label, spin)

    def _add_double_row(
        self,
        form: QtWidgets.QFormLayout,
        field: str,
        label: str,
        min_v: float,
        max_v: float,
        *,
        decimals: int,
    ) -> None:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setObjectName("SettingsInput")
        spin.setRange(min_v, max_v)
        spin.setDecimals(decimals)
        self._doubles[field] = spin
        row_label = QtWidgets.QLabel(label)
        row_label.setObjectName("SettingsFormLabel")
        form.addRow(row_label, spin)

    def refresh(self) -> None:
        thresholds = load_emotion_cycle_thresholds()
        for field, spin in self._spinners.items():
            spin.setValue(int(getattr(thresholds, field)))
        for field, spin in self._doubles.items():
            spin.setValue(float(getattr(thresholds, field)))
        self._hysteresis_check.setChecked(thresholds.hysteresis_enabled)

    def collect_thresholds(self) -> EmotionCycleThresholds:
        payload: dict[str, float | int | bool] = {}
        for field, spin in self._spinners.items():
            payload[field] = spin.value()
        for field, spin in self._doubles.items():
            payload[field] = spin.value()
        payload["hysteresis_enabled"] = self._hysteresis_check.isChecked()
        return EmotionCycleThresholds.model_validate(payload)

    def save_thresholds(self) -> bool:
        thresholds = self.collect_thresholds()
        previous = load_emotion_cycle_thresholds()
        if thresholds == previous:
            return False
        save_emotion_cycle_thresholds(thresholds)
        invalidate_emotion_cycle_cache()
        reset_emotion_stage_hysteresis()
        return True

    def _reset_defaults(self) -> None:
        if not confirm_action(
            self,
            "恢复默认阈值",
            "将情绪周期判定阈值恢复为系统默认值，是否继续？",
            confirm_text="恢复",
        ):
            return
        reset_emotion_cycle_thresholds()
        invalidate_emotion_cycle_cache()
        reset_emotion_stage_hysteresis()
        self.refresh()
        page_notify(self, "情绪周期阈值已恢复默认", level="success")
