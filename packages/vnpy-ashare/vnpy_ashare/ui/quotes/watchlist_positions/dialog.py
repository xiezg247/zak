"""登记 / 编辑持仓弹窗。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.market_hours import CHINA_TZ
from vnpy_ashare.domain.position_snapshot import PositionRecord


@dataclass(frozen=True)
class PositionFormData:
    cost_price: float
    volume: int
    buy_date: str
    notes: str


class PositionEditDialog(QtWidgets.QDialog):
    def __init__(
        self,
        *,
        title: str,
        symbol_text: str,
        record: PositionRecord | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)

        layout = QtWidgets.QFormLayout(self)
        symbol_label = QtWidgets.QLabel(symbol_text, self)
        layout.addRow("标的", symbol_label)

        self._cost_edit = QtWidgets.QDoubleSpinBox(self)
        self._cost_edit.setRange(0.01, 999999.0)
        self._cost_edit.setDecimals(2)
        self._cost_edit.setSingleStep(0.01)
        layout.addRow("成本价", self._cost_edit)

        self._volume_spin = QtWidgets.QSpinBox(self)
        self._volume_spin.setRange(100, 9_999_900)
        self._volume_spin.setSingleStep(100)
        layout.addRow("持仓量", self._volume_spin)

        self._buy_date = QtWidgets.QDateEdit(self)
        self._buy_date.setCalendarPopup(True)
        self._buy_date.setDisplayFormat("yyyy-MM-dd")
        today = datetime.now(CHINA_TZ).date()
        self._buy_date.setMaximumDate(QtCore.QDate(today.year, today.month, today.day))
        layout.addRow("买入日", self._buy_date)

        self._notes_edit = QtWidgets.QLineEdit(self)
        layout.addRow("备注", self._notes_edit)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        if record is not None:
            self._cost_edit.setValue(record.cost_price)
            self._volume_spin.setValue(record.volume)
            parsed = datetime.strptime(record.buy_date[:10], "%Y-%m-%d").date()
            self._buy_date.setDate(QtCore.QDate(parsed.year, parsed.month, parsed.day))
            self._notes_edit.setText(record.notes)
        else:
            self._cost_edit.setValue(10.0)
            self._volume_spin.setValue(100)
            self._buy_date.setDate(QtCore.QDate(today.year, today.month, today.day))

    def read_form(self) -> PositionFormData:
        buy_qdate = self._buy_date.date()
        buy_date = f"{buy_qdate.year():04d}-{buy_qdate.month():02d}-{buy_qdate.day():02d}"
        return PositionFormData(
            cost_price=float(self._cost_edit.value()),
            volume=int(self._volume_spin.value()),
            buy_date=buy_date,
            notes=self._notes_edit.text().strip(),
        )
