"""自选 / 雷达顶栏风控闸芯片。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.trading.risk import CombinedRiskGateSnapshot
from vnpy_ashare.trading.risk.display import build_risk_gate_chip_tooltip, format_risk_gate_chip_value

__all__ = ["RiskGateChip", "build_risk_gate_chip_tooltip", "format_risk_gate_chip_value"]

_STATE_COLORS: dict[str, str] = {
    "normal": "#2ecc71",
    "caution": "#f1c40f",
    "halt": "#e74c3c",
}


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
