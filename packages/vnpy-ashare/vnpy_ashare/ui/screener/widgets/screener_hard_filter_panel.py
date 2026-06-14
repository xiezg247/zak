"""选股硬过滤设置面板（策略/自动选股共用）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.screener.hard_filter_prefs import (
    PRESET_AGGRESSIVE,
    PRESET_BALANCED,
    PRESET_CONSERVATIVE,
    HardFilterPrefs,
    apply_hard_filter_preset,
    load_hard_filter_prefs,
    save_hard_filter_prefs,
)


class ScreenerHardFilterPanel(QtWidgets.QGroupBox):
    """可折叠硬过滤：排除 ST、停牌、流动性、新股、涨跌停与模板。"""

    prefs_changed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("硬过滤", parent)
        self.setObjectName("ScreenerFormBox")
        self.setCheckable(True)
        self.setChecked(False)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(6)

        preset_row = QtWidgets.QHBoxLayout()
        self._conservative_btn = QtWidgets.QPushButton("保守")
        self._balanced_btn = QtWidgets.QPushButton("均衡")
        self._aggressive_btn = QtWidgets.QPushButton("激进")
        for button, preset_id in (
            (self._conservative_btn, PRESET_CONSERVATIVE),
            (self._balanced_btn, PRESET_BALANCED),
            (self._aggressive_btn, PRESET_AGGRESSIVE),
        ):
            button.setObjectName("SecondaryButton")
            button.clicked.connect(lambda _checked=False, pid=preset_id: self._apply_preset(pid))
            preset_row.addWidget(button)
        preset_row.addStretch()
        layout.addLayout(preset_row)

        form = QtWidgets.QFormLayout()
        form.setSpacing(6)

        self.exclude_st_check = QtWidgets.QCheckBox("排除 ST / *ST")
        self.exclude_st_check.toggled.connect(self._on_changed)
        form.addRow(self.exclude_st_check)

        self.exclude_suspended_check = QtWidgets.QCheckBox("排除停牌")
        self.exclude_suspended_check.toggled.connect(self._on_changed)
        form.addRow(self.exclude_suspended_check)

        self.exclude_new_listing_check = QtWidgets.QCheckBox("排除新股")
        self.exclude_new_listing_check.toggled.connect(self._on_changed)
        form.addRow(self.exclude_new_listing_check)

        self.min_listing_days_spin = QtWidgets.QSpinBox()
        self.min_listing_days_spin.setRange(0, 365)
        self.min_listing_days_spin.setSuffix(" 天")
        self.min_listing_days_spin.valueChanged.connect(self._on_changed)
        form.addRow("上市满", self.min_listing_days_spin)

        self.exclude_limit_board_check = QtWidgets.QCheckBox("排除涨跌停附近")
        self.exclude_limit_board_check.toggled.connect(self._on_changed)
        form.addRow(self.exclude_limit_board_check)

        self.min_amount_spin = QtWidgets.QDoubleSpinBox()
        self.min_amount_spin.setRange(0, 100_000)
        self.min_amount_spin.setDecimals(0)
        self.min_amount_spin.setSuffix(" 万元")
        self.min_amount_spin.valueChanged.connect(self._on_changed)
        form.addRow("最低成交额", self.min_amount_spin)

        self.min_mv_spin = QtWidgets.QDoubleSpinBox()
        self.min_mv_spin.setRange(0, 10_000)
        self.min_mv_spin.setDecimals(0)
        self.min_mv_spin.setSuffix(" 亿元")
        self.min_mv_spin.valueChanged.connect(self._on_changed)
        form.addRow("最低总市值", self.min_mv_spin)

        layout.addLayout(form)

        hint = QtWidgets.QLabel("0 表示不限制；环境变量 RECIPE_* 仍可覆盖上述设置。")
        hint.setObjectName("ScreenerHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.reload()

    def reload(self) -> None:
        prefs = load_hard_filter_prefs()
        widgets = (
            self.exclude_st_check,
            self.exclude_suspended_check,
            self.exclude_new_listing_check,
            self.exclude_limit_board_check,
            self.min_listing_days_spin,
            self.min_amount_spin,
            self.min_mv_spin,
        )
        for widget in widgets:
            widget.blockSignals(True)
        self.exclude_st_check.setChecked(prefs.exclude_st)
        self.exclude_suspended_check.setChecked(prefs.exclude_suspended)
        self.exclude_new_listing_check.setChecked(prefs.exclude_new_listing)
        self.exclude_limit_board_check.setChecked(prefs.exclude_limit_board)
        self.min_listing_days_spin.setValue(prefs.min_listing_days)
        self.min_amount_spin.setValue(prefs.min_amount_wan)
        self.min_mv_spin.setValue(prefs.min_total_mv_yi)
        for widget in widgets:
            widget.blockSignals(False)

    def current_prefs(self) -> HardFilterPrefs:
        return HardFilterPrefs(
            exclude_st=self.exclude_st_check.isChecked(),
            exclude_suspended=self.exclude_suspended_check.isChecked(),
            min_amount_wan=float(self.min_amount_spin.value()),
            min_total_mv_yi=float(self.min_mv_spin.value()),
            exclude_new_listing=self.exclude_new_listing_check.isChecked(),
            min_listing_days=int(self.min_listing_days_spin.value()),
            exclude_limit_board=self.exclude_limit_board_check.isChecked(),
        )

    def _apply_preset(self, preset_id: str) -> None:
        apply_hard_filter_preset(preset_id)
        self.reload()
        self.prefs_changed.emit()

    def _on_changed(self, *_args) -> None:
        save_hard_filter_prefs(self.current_prefs())
        self.prefs_changed.emit()
