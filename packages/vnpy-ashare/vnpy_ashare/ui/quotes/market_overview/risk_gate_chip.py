"""自选 / 雷达顶栏风控闸芯片。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.trading.risk import CombinedRiskGateSnapshot

_STATE_COLORS: dict[str, str] = {
    "normal": "#2ecc71",
    "caution": "#f1c40f",
    "halt": "#e74c3c",
}


def format_risk_gate_chip_value(snapshot: CombinedRiskGateSnapshot) -> str:
    account = snapshot.account
    if account.state == "halt":
        return f"{account.state_label} · 停手"
    if not snapshot.allow_new_positions:
        return f"{account.state_label} · 慎开"
    return account.state_label


def build_risk_gate_chip_tooltip(snapshot: CombinedRiskGateSnapshot) -> str:
    account = snapshot.account
    lines = [
        f"账户闸：{account.state_label}",
        "可新开仓" if snapshot.allow_new_positions else "不建议新开仓",
    ]
    if account.daily_pnl_pct is not None:
        lines.append(f"当日盈亏 {account.daily_pnl_pct:+.2f}%")
    if account.avg_float_pnl_pct is not None:
        lines.append(f"持仓浮盈均值 {account.avg_float_pnl_pct:+.2f}%")
    if account.weekly_drawdown_pct is not None:
        lines.append(f"单周回撤 {account.weekly_drawdown_pct:+.2f}%")
    if account.total_drawdown_pct is not None:
        lines.append(f"总回撤 {account.total_drawdown_pct:+.2f}%")
    if account.halt_until:
        lines.append(f"熔断至 {account.halt_until}")
    if snapshot.emotion is not None:
        pos_max = int(snapshot.emotion.position_pct_max * 100)
        lines.append(f"情绪：{snapshot.emotion.stage_label} · 建议≤{pos_max}%")
    if snapshot.actual_position_pct is not None:
        lines.append(f"实际仓位 {snapshot.actual_position_pct * 100:.1f}%")
    for warning in snapshot.warnings[:3]:
        lines.append(warning)
    for warning in account.warnings[:2]:
        if warning not in lines:
            lines.append(warning)
    lines.append("点击打开风控设置")
    return "\n".join(lines)


class RiskGateChip(QtWidgets.QFrame):
    """账户风控闸 + 合并开仓建议。"""

    clicked = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RiskGateChip")
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(1)

        self._title = QtWidgets.QLabel("风控闸")
        self._title.setObjectName("MarketStatChipLabel")
        self._value = QtWidgets.QLabel("—")
        self._value.setObjectName("MarketStatChipValue")
        layout.addWidget(self._title)
        layout.addWidget(self._value)

        self.set_loading()

    def set_loading(self) -> None:
        self._value.setText("—")
        self._value.setStyleSheet("")
        self.setToolTip("等待持仓与风控参数")

    def apply_snapshot(self, snapshot: CombinedRiskGateSnapshot | None) -> None:
        if snapshot is None:
            self.set_loading()
            return

        self._value.setText(format_risk_gate_chip_value(snapshot))
        color = _STATE_COLORS.get(snapshot.account.state, "#888888")
        self._value.setStyleSheet(f"color: {color}; font-weight: 600;")
        self.setToolTip(build_risk_gate_chip_tooltip(snapshot))

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)
