"""移出持仓时填写卖出价。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel, MutableModel

from datetime import datetime

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.config import format_decimal_field
from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.domain.trading.position import compute_unrealized_pnl


class PositionSellFormData(FrozenModel):
    sell_price: float = Field(description="卖出价格")
    sell_date: str = Field(description="卖出日期")


class PositionSellDialog(QtWidgets.QDialog):
    def __init__(
        self,
        *,
        vt_symbol: str,
        cost_price: float,
        volume: int,
        suggested_price: float | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"移出持仓 · {vt_symbol}")
        self.setMinimumWidth(340)

        layout = QtWidgets.QFormLayout(self)
        layout.addRow("标的", QtWidgets.QLabel(vt_symbol, self))
        layout.addRow("成本价", QtWidgets.QLabel(f"{cost_price:.2f}", self))
        layout.addRow("持仓量", QtWidgets.QLabel(f"{volume} 股", self))

        default_price = suggested_price if suggested_price is not None and suggested_price > 0 else cost_price
        self._price_edit = QtWidgets.QLineEdit(self)
        self._price_edit.setText(format_decimal_field(default_price, places=4))
        validator = QtGui.QDoubleValidator(0.0001, 999_999.0, 4, self._price_edit)
        validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
        self._price_edit.setValidator(validator)
        layout.addRow("卖出价", self._price_edit)

        self._sell_date = QtWidgets.QDateEdit(self)
        self._sell_date.setCalendarPopup(True)
        self._sell_date.setDisplayFormat("yyyy-MM-dd")
        today = datetime.now(CHINA_TZ).date()
        self._sell_date.setDate(QtCore.QDate(today.year, today.month, today.day))
        layout.addRow("卖出日", self._sell_date)

        self._pnl_hint = QtWidgets.QLabel("", self)
        self._pnl_hint.setObjectName("SettingsHint")
        layout.addRow("", self._pnl_hint)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self._cost_price = cost_price
        self._volume = volume
        self._price_edit.textChanged.connect(self._refresh_hint)
        self._refresh_hint()

    def _parse_price(self) -> float | None:
        text = self._price_edit.text().strip()
        if not text:
            return None
        try:
            value = float(text)
        except ValueError:
            return None
        return value if value > 0 else None

    def _refresh_hint(self) -> None:
        price = self._parse_price()
        if price is None:
            self._pnl_hint.setText("请填写有效卖出价")
            return
        _, pnl, pnl_pct = compute_unrealized_pnl(self._cost_price, self._volume, price)
        if pnl is None:
            self._pnl_hint.setText("")
            return
        self._pnl_hint.setText(f"预计已实现 {pnl:+.2f} 元（{pnl_pct:+.2f}%）")

    def read_form(self) -> PositionSellFormData | None:
        price = self._parse_price()
        if price is None:
            return None
        qdate = self._sell_date.date()
        sell_date = f"{qdate.year():04d}-{qdate.month():02d}-{qdate.day():02d}"
        return PositionSellFormData(sell_price=price, sell_date=sell_date)
