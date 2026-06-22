"""交易风控参数对话框（K-01）。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.config.preferences.trading_risk import (
    TradingRiskPrefs,
    load_trading_risk_prefs,
    save_trading_risk_prefs,
)
from vnpy_ashare.trading.risk.drawdown import clear_timed_halt, reset_peak_equity
from vnpy_ashare.trading.risk.realized_pnl import (
    format_realized_pnl_hint,
    resolve_realized_pnl_today,
    today_trade_date,
)
from vnpy_ashare.ui.quotes.watchlist_positions.trade_journal_open import show_today_sell_journal

if TYPE_CHECKING:
    from vnpy_ashare.domain.trading.position import PositionSnapshot


def _localize_dialog_buttons(box: QtWidgets.QDialogButtonBox) -> None:
    ok_btn = box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
    if ok_btn is not None:
        ok_btn.setText("确定")
    cancel_btn = box.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
    if cancel_btn is not None:
        cancel_btn.setText("取消")


class RiskSettingsDialog(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        position_cache: Mapping[str, PositionSnapshot] | None = None,
        on_prefs_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._position_cache = position_cache
        self._on_prefs_changed = on_prefs_changed
        self.setWindowTitle("交易风控设置")
        self.setMinimumWidth(400)

        prefs = load_trading_risk_prefs()
        root = QtWidgets.QVBoxLayout(self)

        tabs = QtWidgets.QTabWidget(self)
        tabs.addTab(self._build_basic_tab(prefs), "基础")
        tabs.addTab(self._build_advanced_tab(prefs), "高级")
        root.addWidget(tabs)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        _localize_dialog_buttons(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_basic_tab(self, prefs: TradingRiskPrefs) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(self)
        layout = QtWidgets.QFormLayout(page)

        self._capital_spin = QtWidgets.QDoubleSpinBox(page)
        self._capital_spin.setRange(0.0, 999_999_999.0)
        self._capital_spin.setDecimals(0)
        self._capital_spin.setSingleStep(10_000.0)
        self._capital_spin.setSuffix(" 元")
        self._capital_spin.setSpecialValueText("未设置")
        self._capital_spin.setToolTip("用于单笔风险计算与持仓实际仓位占比（P-05）")
        if prefs.total_capital is not None:
            self._capital_spin.setValue(prefs.total_capital)
        layout.addRow("总资金", self._capital_spin)

        self._per_trade_spin = QtWidgets.QDoubleSpinBox(page)
        self._per_trade_spin.setRange(0.5, 20.0)
        self._per_trade_spin.setDecimals(1)
        self._per_trade_spin.setSuffix(" %")
        self._per_trade_spin.setValue(prefs.per_trade_risk_pct * 100)
        self._per_trade_spin.setToolTip("单笔最大亏损占总投资的比例，默认 2%")
        layout.addRow("单笔风险上限", self._per_trade_spin)

        self._stop_loss_spin = QtWidgets.QDoubleSpinBox(page)
        self._stop_loss_spin.setRange(1.0, 30.0)
        self._stop_loss_spin.setDecimals(1)
        self._stop_loss_spin.setSuffix(" %")
        self._stop_loss_spin.setValue(prefs.stop_loss_pct * 100)
        self._stop_loss_spin.setToolTip("登记持仓时默认止损比例；极致短线常用 5%")
        layout.addRow("默认止损", self._stop_loss_spin)

        hint = QtWidgets.QLabel(
            "总资金与单笔风险用于登记时的建议股数；风控闸状态见顶栏芯片，仅作提示不阻断记账。",
            page,
        )
        hint.setObjectName("SettingsHint")
        hint.setWordWrap(True)
        layout.addRow(hint)
        return page

    def _build_advanced_tab(self, prefs: TradingRiskPrefs) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(self)
        layout = QtWidgets.QFormLayout(page)

        self._daily_pnl_spin = QtWidgets.QDoubleSpinBox(page)
        self._daily_pnl_spin.setRange(-999.0, 50.0)
        self._daily_pnl_spin.setDecimals(1)
        self._daily_pnl_spin.setSuffix(" %")
        self._daily_pnl_spin.setSpecialValueText("未填写")
        self._daily_pnl_spin.setToolTip("当日已实现+浮亏合计，占资金比例（手动填写，供风控闸评估）")
        if prefs.daily_pnl_pct is not None:
            self._daily_pnl_spin.setValue(prefs.daily_pnl_pct)
        else:
            self._daily_pnl_spin.setValue(-999.0)
        layout.addRow("当日盈亏", self._daily_pnl_spin)

        effective, journal_total, manual = resolve_realized_pnl_today(today_trade_date())
        journal_hint = format_realized_pnl_hint(
            journal_total=journal_total,
            manual=manual,
            effective=effective,
        )
        self._journal_label = QtWidgets.QLabel(journal_hint or "今日暂无登记卖出", page)
        self._journal_label.setObjectName("SettingsHint")
        self._journal_label.setWordWrap(True)
        self._journal_view_button = QtWidgets.QPushButton("查看…", page)
        self._journal_view_button.setObjectName("SecondaryButton")
        self._journal_view_button.setToolTip("查看 / 编辑 / 删除今日登记卖出流水")
        self._journal_view_button.clicked.connect(self._on_view_sell_journal)
        journal_row = QtWidgets.QHBoxLayout()
        journal_row.addWidget(self._journal_label, stretch=1)
        journal_row.addWidget(self._journal_view_button)
        layout.addRow("登记卖出汇总", journal_row)

        self._realized_spin = QtWidgets.QDoubleSpinBox(page)
        self._realized_spin.setRange(-9_999_999.0, 9_999_999.0)
        self._realized_spin.setDecimals(0)
        self._realized_spin.setSuffix(" 元")
        self._realized_spin.setSpecialValueText("未填写")
        self._realized_spin.setToolTip("额外已实现（非登记卖出部分，与流水汇总相加）")
        if prefs.realized_pnl_today is not None:
            self._realized_spin.setValue(prefs.realized_pnl_today)
        layout.addRow("额外已实现", self._realized_spin)

        self._caution_daily_spin = QtWidgets.QDoubleSpinBox(page)
        self._caution_daily_spin.setRange(-50.0, 0.0)
        self._caution_daily_spin.setDecimals(1)
        self._caution_daily_spin.setSuffix(" %")
        self._caution_daily_spin.setValue(prefs.caution_daily_pct)
        layout.addRow("警戒阈值（日）", self._caution_daily_spin)

        self._halt_daily_spin = QtWidgets.QDoubleSpinBox(page)
        self._halt_daily_spin.setRange(-50.0, 0.0)
        self._halt_daily_spin.setDecimals(1)
        self._halt_daily_spin.setSuffix(" %")
        self._halt_daily_spin.setValue(prefs.halt_daily_pct)
        layout.addRow("熔断阈值（日）", self._halt_daily_spin)

        self._caution_float_spin = QtWidgets.QDoubleSpinBox(page)
        self._caution_float_spin.setRange(-50.0, 0.0)
        self._caution_float_spin.setDecimals(1)
        self._caution_float_spin.setSuffix(" %")
        self._caution_float_spin.setValue(prefs.caution_float_pct)
        layout.addRow("警戒阈值（持仓均浮盈）", self._caution_float_spin)

        self._manual_halt = QtWidgets.QCheckBox("手动熔断（不建议新开仓提示）", page)
        self._manual_halt.setChecked(prefs.manual_halt)
        layout.addRow("", self._manual_halt)

        self._peak_label = QtWidgets.QLabel(self._format_peak_hint(prefs), page)
        self._peak_label.setObjectName("SettingsHint")
        self._peak_label.setWordWrap(True)
        layout.addRow("权益峰值", self._peak_label)

        peak_row = QtWidgets.QHBoxLayout()
        self._reset_peak_button = QtWidgets.QPushButton("重置峰值", page)
        self._reset_peak_button.setToolTip("以当前权益重置峰值，并清除定时熔断")
        self._reset_peak_button.clicked.connect(self._on_reset_peak)
        self._clear_halt_button = QtWidgets.QPushButton("解除定时熔断", page)
        self._clear_halt_button.setToolTip("清除单周/总回撤触发的停手期限")
        self._clear_halt_button.clicked.connect(self._on_clear_halt)
        peak_row.addWidget(self._reset_peak_button)
        peak_row.addWidget(self._clear_halt_button)
        peak_row.addStretch(1)
        layout.addRow("", peak_row)
        return page

    @staticmethod
    def _format_peak_hint(prefs: TradingRiskPrefs) -> str:
        parts: list[str] = []
        if prefs.peak_equity is not None:
            parts.append(f"峰值 {prefs.peak_equity:,.0f} 元")
        if prefs.halt_until:
            reason = "总回撤" if prefs.halt_reason == "total_drawdown" else "单周回撤"
            parts.append(f"{reason}停手至 {prefs.halt_until}")
        return " · ".join(parts) if parts else "未追踪（需设置总资金）"

    def _refresh_journal_hint(self) -> None:
        effective, journal_total, manual = resolve_realized_pnl_today(today_trade_date())
        journal_hint = format_realized_pnl_hint(
            journal_total=journal_total,
            manual=manual,
            effective=effective,
        )
        self._journal_label.setText(journal_hint or "今日暂无登记卖出")

    def _on_view_sell_journal(self) -> None:
        show_today_sell_journal(self, on_changed=self._on_sell_journal_changed)

    def _on_sell_journal_changed(self) -> None:
        self._refresh_journal_hint()
        self._notify_prefs_changed()

    def _notify_prefs_changed(self) -> None:
        if self._on_prefs_changed is not None:
            self._on_prefs_changed()

    def _on_reset_peak(self) -> None:
        capital = self._capital_spin.value()
        reset_peak_equity(
            total_capital=None if capital <= 0 else capital,
            position_cache=self._position_cache,
        )
        prefs = load_trading_risk_prefs()
        self._peak_label.setText(self._format_peak_hint(prefs))
        self._notify_prefs_changed()

    def _on_clear_halt(self) -> None:
        clear_timed_halt()
        prefs = load_trading_risk_prefs()
        self._peak_label.setText(self._format_peak_hint(prefs))
        self._notify_prefs_changed()

    def read_prefs(self) -> TradingRiskPrefs:
        capital = self._capital_spin.value()
        daily_val = self._daily_pnl_spin.value()
        daily_pnl: float | None = None if daily_val <= -998.9 else daily_val
        realized_val = self._realized_spin.value()
        realized = realized_val if realized_val != 0.0 else None
        existing = load_trading_risk_prefs()
        return existing.model_copy(
            update={
                "total_capital": None if capital <= 0 else capital,
                "per_trade_risk_pct": self._per_trade_spin.value() / 100.0,
                "stop_loss_pct": self._stop_loss_spin.value() / 100.0,
                "daily_pnl_pct": daily_pnl,
                "realized_pnl_today": realized,
                "caution_daily_pct": self._caution_daily_spin.value(),
                "halt_daily_pct": self._halt_daily_spin.value(),
                "caution_float_pct": self._caution_float_spin.value(),
                "manual_halt": self._manual_halt.isChecked(),
            },
        ).normalized()

    @staticmethod
    def open_and_save(
        parent: QtWidgets.QWidget | None = None,
        *,
        position_cache: Mapping[str, PositionSnapshot] | None = None,
        on_prefs_changed: Callable[[], None] | None = None,
    ) -> bool:
        dialog = RiskSettingsDialog(
            parent,
            position_cache=position_cache,
            on_prefs_changed=on_prefs_changed,
        )
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return False
        save_trading_risk_prefs(dialog.read_prefs())
        if on_prefs_changed is not None:
            on_prefs_changed()
        return True
