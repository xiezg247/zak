"""选股硬过滤设置面板（策略/自动选股共用）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.config.trading_universe import get_trading_allowed_boards, trading_boards_hint
from vnpy_ashare.integrations.tushare.factors import fetch_industry_l2_to_l1_map, fetch_stock_industry_map
from vnpy_ashare.integrations.tushare.sw_industry import build_grouped_l2_industries, format_industry_filter_label
from vnpy_ashare.ui.quotes.market_overview.industry_filter_combo import resolve_industry_name
from vnpy_ashare.screener.hard_filter_prefs import (
    MARKET_BOARD_FILTER_OPTIONS,
    PRESET_AGGRESSIVE,
    PRESET_BALANCED,
    PRESET_CONSERVATIVE,
    HardFilterPrefs,
    apply_hard_filter_preset,
    load_hard_filter_prefs,
    normalize_allowed_industries_text,
    normalize_allowed_market_boards_text,
    parse_allowed_industries,
    parse_allowed_market_boards,
    save_hard_filter_prefs,
)


class ScreenerHardFilterPanel(QtWidgets.QGroupBox):
    """硬过滤：排除 ST、停牌、流动性、新股、涨跌停与模板。"""

    prefs_changed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("硬过滤", parent)
        self.setObjectName("ScreenerFormBox")
        self._industry_names: list[str] = []
        self._l2_to_l1: dict[str, str] = {}
        self._market_board_checks: dict[str, QtWidgets.QCheckBox] = {}
        self._board_hint = QtWidgets.QLabel("")
        self._board_hint.setObjectName("ScreenerHint")
        self._board_hint.setWordWrap(True)
        self._board_hint.hide()

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

        board_row = QtWidgets.QWidget()
        board_layout = QtWidgets.QHBoxLayout(board_row)
        board_layout.setContentsMargins(0, 0, 0, 0)
        board_layout.setSpacing(8)
        for label in MARKET_BOARD_FILTER_OPTIONS:
            check = QtWidgets.QCheckBox(label)
            check.toggled.connect(self._on_changed)
            self._market_board_checks[label] = check
            board_layout.addWidget(check)
        board_layout.addStretch()
        form.addRow("市场板块", board_row)
        form.addRow("", self._board_hint)

        self.allowed_industries_combo = QtWidgets.QComboBox()
        self.allowed_industries_combo.setObjectName("ToolbarCombo")
        self.allowed_industries_combo.setEditable(True)
        self.allowed_industries_combo.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        line_edit = self.allowed_industries_combo.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText("输入关键词搜索，如 工业金属；选中后追加，可多选逗号分隔")
            line_edit.setClearButtonEnabled(True)
            line_edit.editingFinished.connect(self._on_industry_text_edited)
        self.allowed_industries_combo.activated.connect(self._on_industry_selected)
        form.addRow("限定行业", self.allowed_industries_combo)

        layout.addLayout(form)

        hint = QtWidgets.QLabel(
            "未勾选市场板块表示不限（若已配置 ASHARE_TRADING_BOARDS 则退回账户可交易范围）；0 表示不限制；环境变量 RECIPE_* 仍可覆盖上述设置。"
        )
        hint.setObjectName("ScreenerHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._load_industry_combo_items()
        self.reload()

    @property
    def allowed_industries_edit(self) -> QtWidgets.QLineEdit | None:
        """兼容旧测试/调用方。"""
        return self.allowed_industries_combo.lineEdit()

    def _load_industry_combo_items(self) -> None:
        try:
            self._industry_names = sorted(
                {name.strip() for name in fetch_stock_industry_map().values() if str(name).strip()}
            )
            self._l2_to_l1 = fetch_industry_l2_to_l1_map()
        except Exception:
            self._industry_names = []
            self._l2_to_l1 = {}

        display_labels = [
            format_industry_filter_label(l2, self._l2_to_l1.get(l2)) for l2 in self._industry_names
        ]

        self.allowed_industries_combo.blockSignals(True)
        self.allowed_industries_combo.clear()
        grouped = build_grouped_l2_industries(self._industry_names, self._l2_to_l1)
        first_group = True
        for _l1, l2_list in grouped:
            if not first_group:
                self.allowed_industries_combo.insertSeparator(self.allowed_industries_combo.count())
            first_group = False
            for l2 in l2_list:
                self.allowed_industries_combo.addItem(
                    format_industry_filter_label(l2, self._l2_to_l1.get(l2)),
                    l2,
                )
        self.allowed_industries_combo.blockSignals(False)

        if not self._industry_names:
            return
        completer = QtWidgets.QCompleter(display_labels, self.allowed_industries_combo)
        completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
        self.allowed_industries_combo.setCompleter(completer)

    def _resolve_industry_token(self, token: str) -> str:
        cleaned = str(token or "").strip()
        if not cleaned:
            return ""
        resolved = resolve_industry_name(cleaned, frozenset(self._industry_names))
        return resolved or cleaned

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
        for check in self._market_board_checks.values():
            check.blockSignals(True)
        self.allowed_industries_combo.blockSignals(True)

        self.exclude_st_check.setChecked(prefs.exclude_st)
        self.exclude_suspended_check.setChecked(prefs.exclude_suspended)
        self.exclude_new_listing_check.setChecked(prefs.exclude_new_listing)
        self.exclude_limit_board_check.setChecked(prefs.exclude_limit_board)
        self.min_listing_days_spin.setValue(prefs.min_listing_days)
        self.min_amount_spin.setValue(prefs.min_amount_wan)
        self.min_mv_spin.setValue(prefs.min_total_mv_yi)

        selected_boards = parse_allowed_market_boards(prefs.allowed_market_boards)
        for label, check in self._market_board_checks.items():
            check.setChecked(label in selected_boards)

        line_edit = self.allowed_industries_combo.lineEdit()
        if line_edit is not None:
            line_edit.setText(prefs.allowed_industries)

        for widget in widgets:
            widget.blockSignals(False)
        for check in self._market_board_checks.values():
            check.blockSignals(False)
        self.allowed_industries_combo.blockSignals(False)
        self._apply_trading_board_ceiling()

    def _apply_trading_board_ceiling(self) -> None:
        ceiling = get_trading_allowed_boards()
        hint = trading_boards_hint()
        if hint:
            self._board_hint.setText(f"账户可交易板块：{hint}（不可超出此范围）")
            self._board_hint.show()
        else:
            self._board_hint.hide()

        for label, check in self._market_board_checks.items():
            if ceiling and label not in ceiling:
                check.blockSignals(True)
                check.setChecked(False)
                check.setEnabled(False)
                check.blockSignals(False)
            else:
                check.setEnabled(True)

    def current_prefs(self) -> HardFilterPrefs:
        ceiling = get_trading_allowed_boards()
        selected_boards = [label for label, check in self._market_board_checks.items() if check.isChecked()]
        if ceiling:
            selected_boards = [label for label in selected_boards if label in ceiling]
        industries_text = ""
        line_edit = self.allowed_industries_combo.lineEdit()
        if line_edit is not None:
            industries_text = line_edit.text()
        return HardFilterPrefs(
            exclude_st=self.exclude_st_check.isChecked(),
            exclude_suspended=self.exclude_suspended_check.isChecked(),
            min_amount_wan=float(self.min_amount_spin.value()),
            min_total_mv_yi=float(self.min_mv_spin.value()),
            exclude_new_listing=self.exclude_new_listing_check.isChecked(),
            min_listing_days=int(self.min_listing_days_spin.value()),
            exclude_limit_board=self.exclude_limit_board_check.isChecked(),
            allowed_industries=normalize_allowed_industries_text(industries_text),
            allowed_market_boards=normalize_allowed_market_boards_text(",".join(selected_boards)),
        )

    def _apply_preset(self, preset_id: str) -> None:
        current_industries = self.current_prefs().allowed_industries
        current_boards = self.current_prefs().allowed_market_boards
        apply_hard_filter_preset(preset_id)
        self.reload()
        if current_industries or current_boards:
            prefs = self.current_prefs()
            save_hard_filter_prefs(
                HardFilterPrefs(
                    exclude_st=prefs.exclude_st,
                    exclude_suspended=prefs.exclude_suspended,
                    min_amount_wan=prefs.min_amount_wan,
                    min_total_mv_yi=prefs.min_total_mv_yi,
                    exclude_new_listing=prefs.exclude_new_listing,
                    min_listing_days=prefs.min_listing_days,
                    exclude_limit_board=prefs.exclude_limit_board,
                    allowed_industries=current_industries,
                    allowed_market_boards=current_boards,
                )
            )
            self.reload()
        self.prefs_changed.emit()

    def _on_industry_selected(self, index: int) -> None:
        if index < 0:
            return
        picked = str(self.allowed_industries_combo.itemData(index) or "").strip()
        if not picked:
            picked = self._resolve_industry_token(self.allowed_industries_combo.itemText(index))
        if not picked:
            return
        line_edit = self.allowed_industries_combo.lineEdit()
        if line_edit is None:
            return
        current = parse_allowed_industries(line_edit.text())
        merged = normalize_allowed_industries_text(",".join(sorted(current | {picked})))
        line_edit.setText(merged)
        self.allowed_industries_combo.setCurrentIndex(-1)
        self._on_changed()

    def _on_industry_text_edited(self) -> None:
        line_edit = self.allowed_industries_combo.lineEdit()
        if line_edit is None:
            return
        raw = line_edit.text()
        parts = [part.strip() for part in raw.replace("，", ",").split(",") if part.strip()]
        resolved_parts = [self._resolve_industry_token(part) for part in parts]
        normalized = normalize_allowed_industries_text(",".join(resolved_parts))
        if line_edit.text() != normalized:
            line_edit.setText(normalized)
        self._on_changed()

    def _on_changed(self, *_args) -> None:
        save_hard_filter_prefs(self.current_prefs())
        self.prefs_changed.emit()
