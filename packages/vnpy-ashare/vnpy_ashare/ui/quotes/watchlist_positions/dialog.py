"""登记 / 编辑持仓弹窗。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.config import format_decimal_field
from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.domain.trading.position import PositionRecord
from vnpy_ashare.trading.risk.plan_position import normalize_plan_pct
from vnpy_ashare.trading.risk.position_size import (
    compute_position_size_from_prefs,
    format_position_size_hint,
)

_COST_PRICE_PLACES = 4


@dataclass(frozen=True)
class PositionFormData:
    cost_price: float
    volume: int
    buy_date: str
    notes: str
    plan_pct: float | None = None


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

        self._cost_edit = QtWidgets.QLineEdit(self)
        self._cost_edit.setPlaceholderText("如 10.55")
        cost_validator = QtGui.QDoubleValidator(0.0001, 999_999.0, _COST_PRICE_PLACES, self._cost_edit)
        cost_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
        self._cost_edit.setValidator(cost_validator)
        layout.addRow("成本价", self._cost_edit)

        self._volume_spin = QtWidgets.QSpinBox(self)
        self._volume_spin.setRange(100, 9_999_900)
        self._volume_spin.setSingleStep(100)
        self._volume_spin.setSuffix(" 股")
        self._volume_spin.setToolTip("按股数填写，须为 100 的整数倍（1 手 = 100 股）")
        layout.addRow("持仓量（股）", self._volume_spin)

        self._buy_date = QtWidgets.QDateEdit(self)
        self._buy_date.setCalendarPopup(True)
        self._buy_date.setDisplayFormat("yyyy-MM-dd")
        today = datetime.now(CHINA_TZ).date()
        self._buy_date.setMaximumDate(QtCore.QDate(today.year, today.month, today.day))
        layout.addRow("买入日", self._buy_date)

        self._notes_edit = QtWidgets.QLineEdit(self)
        layout.addRow("备注", self._notes_edit)

        self._plan_check = QtWidgets.QCheckBox("设定计划仓位", self)
        self._plan_spin = QtWidgets.QDoubleSpinBox(self)
        self._plan_spin.setRange(1.0, 50.0)
        self._plan_spin.setDecimals(1)
        self._plan_spin.setSingleStep(1.0)
        self._plan_spin.setSuffix(" %")
        self._plan_spin.setToolTip("相对总资金的单票计划占比（需在风控设置中填写总资金）")
        plan_row = QtWidgets.QHBoxLayout()
        plan_row.addWidget(self._plan_check)
        plan_row.addWidget(self._plan_spin, 1)
        plan_widget = QtWidgets.QWidget(self)
        plan_widget.setLayout(plan_row)
        layout.addRow("计划仓位", plan_widget)
        self._plan_check.toggled.connect(self._plan_spin.setEnabled)
        self._plan_spin.setEnabled(False)

        self._risk_hint = QtWidgets.QLabel("", self)
        self._risk_hint.setObjectName("SettingsHint")
        self._risk_hint.setWordWrap(True)
        layout.addRow("", self._risk_hint)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        if record is not None:
            self._cost_edit.setText(format_decimal_field(record.cost_price, places=_COST_PRICE_PLACES))
            self._volume_spin.setValue(record.volume)
            parsed = datetime.strptime(record.buy_date[:10], "%Y-%m-%d").date()
            self._buy_date.setDate(QtCore.QDate(parsed.year, parsed.month, parsed.day))
            self._notes_edit.setText(record.notes)
            if record.plan_pct is not None and record.plan_pct > 0:
                self._plan_check.setChecked(True)
                self._plan_spin.setEnabled(True)
                self._plan_spin.setValue(round(record.plan_pct * 100, 1))
        else:
            self._cost_edit.setText(format_decimal_field(10.0, places=_COST_PRICE_PLACES))
            self._volume_spin.setValue(100)
            self._buy_date.setDate(QtCore.QDate(today.year, today.month, today.day))

        self._cost_edit.textChanged.connect(self._refresh_risk_hint)
        self._volume_spin.valueChanged.connect(self._refresh_risk_hint)
        self._refresh_risk_hint()

    def _refresh_risk_hint(self) -> None:
        cost = self._parse_cost_price()
        volume = int(self._volume_spin.value())
        if cost is None:
            self._risk_hint.setText(format_position_size_hint(None))
            return
        result = compute_position_size_from_prefs(cost_price=cost, requested_volume=volume)
        self._risk_hint.setText(format_position_size_hint(result))

    def _parse_cost_price(self) -> float | None:
        text = self._cost_edit.text().strip()
        if not text:
            return None
        try:
            value = float(text)
        except ValueError:
            return None
        if value <= 0:
            return None
        return value

    def read_form(self) -> PositionFormData:
        buy_qdate = self._buy_date.date()
        buy_date = f"{buy_qdate.year():04d}-{buy_qdate.month():02d}-{buy_qdate.day():02d}"
        cost_price = self._parse_cost_price()
        if cost_price is None:
            cost_price = 0.0
        plan_pct = None
        if self._plan_check.isChecked():
            plan_pct = normalize_plan_pct(self._plan_spin.value() / 100.0)
        return PositionFormData(
            cost_price=cost_price,
            volume=int(self._volume_spin.value()),
            buy_date=buy_date,
            notes=self._notes_edit.text().strip(),
            plan_pct=plan_pct,
        )
