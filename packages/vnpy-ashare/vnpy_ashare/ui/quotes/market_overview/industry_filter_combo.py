"""市场页概览：可搜索行业筛选。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.services.industry_sector import (
    build_grouped_l2_industries,
    fetch_industry_l2_to_l1_map,
    fetch_stock_industry_map,
    fetch_sw_l2_index_map,
    format_industry_filter_label,
    get_cached_industry_map,
)
from vnpy_ashare.ui.styles.vnpy_page import apply_toolbar_combo_style


def resolve_industry_name(text: str, industries: frozenset[str]) -> str | None:
    """将用户输入解析为唯一行业名；无法唯一匹配时返回 None。"""
    cleaned = str(text or "").strip()
    if not cleaned:
        return None
    if cleaned in industries:
        return cleaned
    if " / " in cleaned:
        tail = cleaned.rsplit(" / ", 1)[-1].strip()
        if tail in industries:
            return tail
        cleaned = tail
    exact_ci = [name for name in industries if name.lower() == cleaned.lower()]
    if len(exact_ci) == 1:
        return exact_ci[0]
    contains = [name for name in industries if cleaned in name]
    if len(contains) == 1:
        return contains[0]
    return None


def resolve_industry_for_drilldown(
    industry: str,
    *,
    sector_id: str | None = None,
) -> str | None:
    """板块资金等下钻：解析为市场页申万 L2 行业筛选名。"""
    name = str(industry or "").strip()
    index_code = str(sector_id or "").strip()
    if index_code:
        for l2_name, code in fetch_sw_l2_index_map().items():
            if code == index_code:
                name = l2_name
                break

    mapping = get_cached_industry_map() or fetch_stock_industry_map()
    industries = frozenset({str(v).strip() for v in mapping.values() if str(v).strip()})
    return resolve_industry_name(name, industries)


class IndustryFilterCombo(QtWidgets.QWidget):
    """Tushare 行业筛选：可编辑下拉 + 自动补全。"""

    industry_selected = QtCore.Signal(str)
    industry_cleared = QtCore.Signal()
    industry_invalid = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MarketIndustryFilter")
        self._industries: list[str] = []
        self._industry_set: frozenset[str] = frozenset()
        self._l2_to_l1: dict[str, str] = {}
        self._display_labels: list[str] = []
        self._active_industry: str | None = None
        self._syncing = False

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._combo = QtWidgets.QComboBox(self)
        self._combo.setObjectName("MarketIndustryCombo")
        self._combo.setEditable(True)
        self._combo.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self._combo.setMinimumWidth(140)
        self._combo.setMaximumWidth(200)
        apply_toolbar_combo_style(self._combo)
        self._combo.setObjectName("MarketIndustryCombo")
        line_edit = self._combo.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText("筛选行业，如 工业金属")
            line_edit.setClearButtonEnabled(True)
            line_edit.returnPressed.connect(self._on_commit)
            line_edit.textChanged.connect(self._on_text_changed)

        self._clear_btn = QtWidgets.QToolButton(self)
        self._clear_btn.setObjectName("MarketIndustryClear")
        self._clear_btn.setText("×")
        self._clear_btn.setToolTip("清除行业筛选")
        self._clear_btn.hide()
        self._clear_btn.clicked.connect(self._on_clear_clicked)

        layout.addWidget(self._combo)
        layout.addWidget(self._clear_btn)

        self._combo.activated.connect(self._on_activated)

    def _display_for_l2(self, l2: str) -> str:
        return format_industry_filter_label(l2, self._l2_to_l1.get(l2))

    def ensure_options_loaded(self) -> None:
        if self._industries:
            return

        mapping = get_cached_industry_map() or fetch_stock_industry_map()
        industries = sorted({str(name).strip() for name in mapping.values() if str(name).strip()})
        try:
            l2_to_l1 = fetch_industry_l2_to_l1_map()
        except Exception:
            l2_to_l1 = {}
        self._industries = industries
        self._industry_set = frozenset(industries)
        self._l2_to_l1 = l2_to_l1
        self._display_labels = [self._display_for_l2(l2) for l2 in industries]

        self._combo.blockSignals(True)
        self._combo.clear()
        grouped = build_grouped_l2_industries(industries, l2_to_l1)
        first_group = True
        for _l1, l2_list in grouped:
            if not first_group:
                self._combo.insertSeparator(self._combo.count())
            first_group = False
            for l2 in l2_list:
                self._combo.addItem(self._display_for_l2(l2), l2)
        self._combo.blockSignals(False)

        completer = QtWidgets.QCompleter(self._display_labels, self._combo)
        completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
        self._combo.setCompleter(completer)

    def set_industry(self, industry: str | None) -> None:
        self._syncing = True
        try:
            self._active_industry = str(industry).strip() if industry else None
            if self._active_industry:
                self._combo.setCurrentText(self._display_for_l2(self._active_industry))
                self._clear_btn.show()
            else:
                self._combo.setCurrentIndex(-1)
                line_edit = self._combo.lineEdit()
                if line_edit is not None:
                    line_edit.clear()
                self._clear_btn.hide()
        finally:
            self._syncing = False

    def _on_text_changed(self, text: str) -> None:
        if self._syncing:
            return
        if not str(text or "").strip() and self._active_industry:
            self._on_clear_clicked()

    def _on_activated(self, index: int) -> None:
        if self._syncing or index < 0:
            return
        industry = str(self._combo.itemData(index) or self._combo.itemText(index)).strip()
        if not industry:
            return
        if industry == self._active_industry:
            return
        self._active_industry = industry
        self._clear_btn.show()
        self.industry_selected.emit(industry)

    def _on_commit(self) -> None:
        if self._syncing:
            return
        text = self._combo.currentText()
        if not str(text or "").strip():
            if self._active_industry:
                self._on_clear_clicked()
            return
        resolved = resolve_industry_name(text, self._industry_set)
        if resolved is None:
            if str(text or "").strip():
                self.industry_invalid.emit(str(text).strip())
            if self._active_industry:
                self.set_industry(self._active_industry)
            return
        if resolved == self._active_industry:
            return
        self._active_industry = resolved
        self._combo.setCurrentText(self._display_for_l2(resolved))
        self._clear_btn.show()
        self.industry_selected.emit(resolved)

    def _on_clear_clicked(self) -> None:
        if not self._active_industry:
            return
        self.set_industry(None)
        self.industry_cleared.emit()
