"""选股硬过滤设置面板（策略/自动选股共用）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.screener.hard_filter_prefs import (
    HardFilterPrefs,
    load_hard_filter_prefs,
    save_hard_filter_prefs,
)


class ScreenerHardFilterPanel(QtWidgets.QGroupBox):
    """可折叠硬过滤：排除 ST、停牌、最低成交额、最低总市值。"""

    prefs_changed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("硬过滤", parent)
        self.setObjectName("ScreenerFormBox")
        self.setCheckable(True)
        self.setChecked(False)

        layout = QtWidgets.QFormLayout(self)
        layout.setSpacing(6)

        self.exclude_st_check = QtWidgets.QCheckBox("排除 ST / *ST")
        self.exclude_st_check.toggled.connect(self._on_changed)
        layout.addRow(self.exclude_st_check)

        self.exclude_suspended_check = QtWidgets.QCheckBox("排除停牌")
        self.exclude_suspended_check.toggled.connect(self._on_changed)
        layout.addRow(self.exclude_suspended_check)

        self.min_amount_spin = QtWidgets.QDoubleSpinBox()
        self.min_amount_spin.setRange(0, 100_000)
        self.min_amount_spin.setDecimals(0)
        self.min_amount_spin.setSuffix(" 万元")
        self.min_amount_spin.valueChanged.connect(self._on_changed)
        layout.addRow("最低成交额", self.min_amount_spin)

        self.min_mv_spin = QtWidgets.QDoubleSpinBox()
        self.min_mv_spin.setRange(0, 10_000)
        self.min_mv_spin.setDecimals(0)
        self.min_mv_spin.setSuffix(" 亿元")
        self.min_mv_spin.valueChanged.connect(self._on_changed)
        layout.addRow("最低总市值", self.min_mv_spin)

        hint = QtWidgets.QLabel("0 表示不限制；环境变量 RECIPE_* 仍可覆盖上述设置。")
        hint.setObjectName("ScreenerHint")
        hint.setWordWrap(True)
        layout.addRow(hint)

        self.reload()

    def reload(self) -> None:
        prefs = load_hard_filter_prefs()
        self.exclude_st_check.blockSignals(True)
        self.exclude_suspended_check.blockSignals(True)
        self.min_amount_spin.blockSignals(True)
        self.min_mv_spin.blockSignals(True)
        self.exclude_st_check.setChecked(prefs.exclude_st)
        self.exclude_suspended_check.setChecked(prefs.exclude_suspended)
        self.min_amount_spin.setValue(prefs.min_amount_wan)
        self.min_mv_spin.setValue(prefs.min_total_mv_yi)
        self.exclude_st_check.blockSignals(False)
        self.exclude_suspended_check.blockSignals(False)
        self.min_amount_spin.blockSignals(False)
        self.min_mv_spin.blockSignals(False)

    def current_prefs(self) -> HardFilterPrefs:
        return HardFilterPrefs(
            exclude_st=self.exclude_st_check.isChecked(),
            exclude_suspended=self.exclude_suspended_check.isChecked(),
            min_amount_wan=float(self.min_amount_spin.value()),
            min_total_mv_yi=float(self.min_mv_spin.value()),
        )

    def _on_changed(self, *_args) -> None:
        save_hard_filter_prefs(self.current_prefs())
        self.prefs_changed.emit()
