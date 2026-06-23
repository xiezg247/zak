"""Playbook 首屏对照条。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.domain.trading.playbook import HomePlaybookStatus


class HomePlaybookStatusStrip(QtWidgets.QFrame):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomePlaybookStatusStrip")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self._alert = QtWidgets.QLabel("")
        self._alert.setObjectName("HomePlaybookAlert")
        self._alert.setWordWrap(True)
        self._alert.hide()

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(16)
        self._chips: list[QtWidgets.QLabel] = []
        for _ in range(5):
            chip = QtWidgets.QLabel("—")
            chip.setObjectName("MarketStatChipValue")
            chip.setWordWrap(True)
            self._chips.append(chip)
            row.addWidget(chip, stretch=1)
        layout.addWidget(self._alert)
        layout.addLayout(row)

    def apply(self, status: HomePlaybookStatus) -> None:
        values = [
            f"情绪：{status.emotion_label}\n{status.emotion_position_hint}",
            f"风控：{status.risk_label}\n{'可开仓' if status.allow_new_positions else '禁新开'}",
            f"日盈亏：{status.daily_pnl_text}",
            status.plan_text,
            f"{status.position_text}\n{status.discipline_progress}".strip(),
        ]
        for index, (chip, text) in enumerate(zip(self._chips, values, strict=True)):
            chip.setText(text)
            if not status.allow_new_positions and index == 1:
                chip.setStyleSheet("color: #e74c3c; font-weight: 600;")
            elif status.off_plan_symbols and index == 4:
                chip.setStyleSheet("color: #e74c3c; font-weight: 600;")
            else:
                chip.setStyleSheet("")

        if status.alert:
            self._alert.setText(status.alert)
            self._alert.setStyleSheet(
                "color: #e74c3c; font-weight: 600;" if status.off_plan_symbols else ""
            )
            self._alert.show()
        else:
            self._alert.hide()
            self._alert.setStyleSheet("")
