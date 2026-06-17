"""交易风控参数对话框（K-01）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.config.preferences.trading_risk import (
    TradingRiskPrefs,
    load_trading_risk_prefs,
    save_trading_risk_prefs,
)
from vnpy_ashare.trading.risk.realized_pnl import (
    format_realized_pnl_hint,
    resolve_realized_pnl_today,
    today_trade_date,
)


class RiskSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("交易风控设置")
        self.setMinimumWidth(400)

        prefs = load_trading_risk_prefs()
        layout = QtWidgets.QFormLayout(self)

        self._capital_spin = QtWidgets.QDoubleSpinBox(self)
        self._capital_spin.setRange(0.0, 999_999_999.0)
        self._capital_spin.setDecimals(0)
        self._capital_spin.setSingleStep(10_000.0)
        self._capital_spin.setSuffix(" 元")
        self._capital_spin.setSpecialValueText("未设置")
        self._capital_spin.setToolTip("用于单笔风险计算与持仓实际仓位占比（P-05）")
        if prefs.total_capital is not None:
            self._capital_spin.setValue(prefs.total_capital)
        layout.addRow("总资金", self._capital_spin)

        self._per_trade_spin = QtWidgets.QDoubleSpinBox(self)
        self._per_trade_spin.setRange(0.5, 20.0)
        self._per_trade_spin.setDecimals(1)
        self._per_trade_spin.setSuffix(" %")
        self._per_trade_spin.setValue(prefs.per_trade_risk_pct * 100)
        self._per_trade_spin.setToolTip("单笔最大亏损占总投资的比例，默认 2%")
        layout.addRow("单笔风险上限", self._per_trade_spin)

        self._stop_loss_spin = QtWidgets.QDoubleSpinBox(self)
        self._stop_loss_spin.setRange(1.0, 30.0)
        self._stop_loss_spin.setDecimals(1)
        self._stop_loss_spin.setSuffix(" %")
        self._stop_loss_spin.setValue(prefs.stop_loss_pct * 100)
        self._stop_loss_spin.setToolTip("登记持仓时默认止损比例；极致短线常用 5%")
        layout.addRow("默认止损", self._stop_loss_spin)

        self._daily_pnl_edit = QtWidgets.QLineEdit(self)
        self._daily_pnl_edit.setPlaceholderText("留空表示未填写")
        self._daily_pnl_edit.setToolTip("当日已实现+浮亏合计（MVP 手动填写，供风控闸评估）")
        if prefs.daily_pnl_pct is not None:
            self._daily_pnl_edit.setText(f"{prefs.daily_pnl_pct:.1f}")
        layout.addRow("当日盈亏", self._daily_pnl_edit)

        effective, journal_total, manual = resolve_realized_pnl_today(today_trade_date())
        journal_hint = format_realized_pnl_hint(
            journal_total=journal_total,
            manual=manual,
            effective=effective,
        )
        self._journal_label = QtWidgets.QLabel(journal_hint or "今日暂无登记卖出", self)
        self._journal_label.setObjectName("SettingsHint")
        self._journal_label.setWordWrap(True)
        layout.addRow("登记卖出汇总", self._journal_label)

        self._realized_spin = QtWidgets.QDoubleSpinBox(self)
        self._realized_spin.setRange(-9_999_999.0, 9_999_999.0)
        self._realized_spin.setDecimals(0)
        self._realized_spin.setSuffix(" 元")
        self._realized_spin.setSpecialValueText("未填写")
        self._realized_spin.setToolTip("额外已实现（非登记卖出部分，与流水汇总相加）")
        if prefs.realized_pnl_today is not None:
            self._realized_spin.setValue(prefs.realized_pnl_today)
        layout.addRow("额外已实现", self._realized_spin)

        self._caution_daily_spin = QtWidgets.QDoubleSpinBox(self)
        self._caution_daily_spin.setRange(-50.0, 0.0)
        self._caution_daily_spin.setDecimals(1)
        self._caution_daily_spin.setSuffix(" %")
        self._caution_daily_spin.setValue(prefs.caution_daily_pct)
        layout.addRow("警戒阈值（日）", self._caution_daily_spin)

        self._halt_daily_spin = QtWidgets.QDoubleSpinBox(self)
        self._halt_daily_spin.setRange(-50.0, 0.0)
        self._halt_daily_spin.setDecimals(1)
        self._halt_daily_spin.setSuffix(" %")
        self._halt_daily_spin.setValue(prefs.halt_daily_pct)
        layout.addRow("熔断阈值（日）", self._halt_daily_spin)

        self._caution_float_spin = QtWidgets.QDoubleSpinBox(self)
        self._caution_float_spin.setRange(-50.0, 0.0)
        self._caution_float_spin.setDecimals(1)
        self._caution_float_spin.setSuffix(" %")
        self._caution_float_spin.setValue(prefs.caution_float_pct)
        layout.addRow("警戒阈值（持仓均浮盈）", self._caution_float_spin)

        self._manual_halt = QtWidgets.QCheckBox("手动熔断（禁止新开仓提示）", self)
        self._manual_halt.setChecked(prefs.manual_halt)
        layout.addRow("", self._manual_halt)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def read_prefs(self) -> TradingRiskPrefs:
        capital = self._capital_spin.value()
        daily_text = self._daily_pnl_edit.text().strip()
        daily_pnl: float | None = None
        if daily_text:
            try:
                daily_pnl = float(daily_text)
            except ValueError:
                daily_pnl = None
        realized_val = self._realized_spin.value()
        realized = realized_val if realized_val != 0.0 else None
        return TradingRiskPrefs(
            total_capital=None if capital <= 0 else capital,
            per_trade_risk_pct=self._per_trade_spin.value() / 100.0,
            stop_loss_pct=self._stop_loss_spin.value() / 100.0,
            daily_pnl_pct=daily_pnl,
            realized_pnl_today=realized,
            caution_daily_pct=self._caution_daily_spin.value(),
            halt_daily_pct=self._halt_daily_spin.value(),
            caution_float_pct=self._caution_float_spin.value(),
            manual_halt=self._manual_halt.isChecked(),
        ).normalized()

    @staticmethod
    def open_and_save(parent: QtWidgets.QWidget | None = None) -> bool:
        dialog = RiskSettingsDialog(parent)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return False
        save_trading_risk_prefs(dialog.read_prefs())
        return True
