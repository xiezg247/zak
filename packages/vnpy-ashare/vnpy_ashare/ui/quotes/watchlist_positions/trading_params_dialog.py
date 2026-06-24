"""交易参数（总资金、当日已实现等）。"""

from __future__ import annotations

from vnpy.trader.ui import QtGui, QtWidgets

from vnpy_ashare.config.preferences.trading_risk import (
    DEFAULT_CAUTION_FLOAT_PCT,
    DEFAULT_STOP_LOSS_PCT,
    TradingRiskPrefs,
    load_trading_risk_prefs,
    save_trading_risk_prefs,
)


class TradingParamsDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("交易参数")
        self.setMinimumWidth(360)

        prefs = load_trading_risk_prefs()
        layout = QtWidgets.QFormLayout(self)

        self._capital_edit = QtWidgets.QLineEdit(self)
        self._capital_edit.setPlaceholderText("留空则不计算仓位占比")
        if prefs.total_capital is not None:
            self._capital_edit.setText(f"{prefs.total_capital:.0f}")
        cap_validator = QtGui.QDoubleValidator(1.0, 999_999_999.0, 2, self._capital_edit)
        cap_validator.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
        self._capital_edit.setValidator(cap_validator)
        layout.addRow("总资金（元）", self._capital_edit)

        self._realized_edit = QtWidgets.QLineEdit(self)
        self._realized_edit.setPlaceholderText("留空则不在统计栏展示已实现")
        if prefs.realized_pnl_today is not None:
            self._realized_edit.setText(f"{prefs.realized_pnl_today:.2f}")
        layout.addRow("当日已实现（元）", self._realized_edit)

        self._stop_spin = QtWidgets.QDoubleSpinBox(self)
        self._stop_spin.setRange(0.5, 50.0)
        self._stop_spin.setDecimals(1)
        self._stop_spin.setSuffix(" %")
        self._stop_spin.setValue(prefs.stop_loss_pct * 100)
        self._stop_spin.setToolTip("隔日止损规则默认比例")
        layout.addRow("默认止损", self._stop_spin)

        self._float_spin = QtWidgets.QDoubleSpinBox(self)
        self._float_spin.setRange(-50.0, -0.5)
        self._float_spin.setDecimals(1)
        self._float_spin.setSuffix(" %")
        self._float_spin.setValue(prefs.caution_float_pct)
        self._float_spin.setToolTip("浮亏达到该比例时触发持仓异动提醒")
        layout.addRow("浮亏警戒", self._float_spin)

        hint = QtWidgets.QLabel("用于仓位占比与盈亏统计；不构成下单或熔断。", self)
        hint.setWordWrap(True)
        hint.setObjectName("MutedLabel")
        layout.addRow(hint)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @staticmethod
    def _parse_optional_float(text: str) -> float | None:
        raw = text.strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    def _on_accept(self) -> None:
        stop_pct = self._stop_spin.value() / 100.0
        if stop_pct <= 0 or stop_pct > 0.5:
            stop_pct = DEFAULT_STOP_LOSS_PCT
        caution = self._float_spin.value()
        if caution >= 0:
            caution = DEFAULT_CAUTION_FLOAT_PCT
        save_trading_risk_prefs(
            TradingRiskPrefs(
                total_capital=self._parse_optional_float(self._capital_edit.text()),
                stop_loss_pct=stop_pct,
                caution_float_pct=caution,
                realized_pnl_today=self._parse_optional_float(self._realized_edit.text()),
            )
        )
        self.accept()
