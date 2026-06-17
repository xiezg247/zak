"""市场页情绪周期芯片。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.quotes.market.emotion_cycle import EmotionCycleSnapshot, format_mode_label

_STAGE_COLORS: dict[str, str] = {
    "ice": "#3498db",
    "startup": "#2ecc71",
    "climax": "#e74c3c",
    "divergence": "#f1c40f",
    "recession": "#95a5a6",
}


class EmotionCycleChip(QtWidgets.QFrame):
    """情绪阶段 + 建议仓位。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("EmotionCycleChip")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(1)

        self._title = QtWidgets.QLabel("情绪周期")
        self._title.setObjectName("MarketStatChipLabel")
        self._value = QtWidgets.QLabel("—")
        self._value.setObjectName("MarketStatChipValue")
        layout.addWidget(self._title)
        layout.addWidget(self._value)

        self.set_loading()

    def set_loading(self) -> None:
        self._value.setText("—")
        self._value.setStyleSheet("")
        self.setToolTip("等待市场广度数据")

    def render(self, snapshot: EmotionCycleSnapshot | None) -> None:
        if snapshot is None:
            self.set_loading()
            return

        pos_max = int(snapshot.position_pct_max * 100)
        pos_min = int(snapshot.position_pct_min * 100)
        if pos_max <= 0:
            pos_text = "建议空仓"
        elif pos_min == pos_max:
            pos_text = f"建议 {pos_max}%"
        else:
            pos_text = f"建议 {pos_min}–{pos_max}%"

        self._value.setText(f"{snapshot.stage_label} · {pos_text}")
        color = _STAGE_COLORS.get(snapshot.stage, "#888888")
        self._value.setStyleSheet(f"color: {color}; font-weight: 600;")

        lines = [
            f"阶段：{snapshot.stage_label}",
            pos_text,
            f"仓位系数 {snapshot.position_factor:.2f}",
        ]
        if snapshot.allowed_modes:
            labels = "、".join(format_mode_label(mode) for mode in snapshot.allowed_modes)
            lines.append(f"允许模式：{labels}")
        else:
            lines.append("允许模式：无（保守）")
        if not snapshot.allow_new_positions:
            lines.append("不建议短线新开仓")
        for warning in snapshot.warnings:
            lines.append(warning)
        inputs = snapshot.inputs
        lines.append(
            f"涨停 {inputs.get('limit_up_count', '—')} · 跌停 {inputs.get('limit_down_count', '—')} · "
            f"最高板 {inputs.get('max_limit_times', '—')} · 梯队 {inputs.get('limit_ladder_depth', '—')}"
        )
        self.setToolTip("\n".join(lines))
