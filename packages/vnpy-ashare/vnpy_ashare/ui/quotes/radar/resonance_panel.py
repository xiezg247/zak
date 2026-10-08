"""雷达页共振列表侧栏。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.quotes.radar.loaders import RadarResonanceEntry
from vnpy_ashare.ui.components.splitter_utils import set_splitter_sizes_quiet
from vnpy_ashare.ui.quotes.radar.resonance_chrome import (
    build_resonance_body,
    build_resonance_handle,
    build_resonance_header,
    build_resonance_tabs,
    build_resonance_toolbar,
)
from vnpy_ashare.ui.quotes.radar.resonance_layout import (
    COLLAPSE_BUTTON_SIZE,
    RESONANCE_COLLAPSED_WIDTH,
    RESONANCE_CONTENT_MAX_WIDTH,
    RESONANCE_CONTENT_MIN_WIDTH,
    RESONANCE_EXPANDED_DEFAULT_WIDTH,
    RESONANCE_EXPANDED_MIN_WIDTH,
    RESONANCE_HANDLE_WIDTH,
    RESONANCE_TABS,
    RadarResonanceTab,
    ResonanceFilterMode,
    apply_resonance_filters,
    collapse_button_tooltip,
    format_resonance_stats,
    gate_banner_text,
    parse_filter_mode,
    resonance_action_state,
    risk_banner_text,
)
from vnpy_ashare.ui.quotes.radar.resonance_row_widget import RadarResonanceRowWidget
from vnpy_ashare.ui.quotes.radar.section_prefs import (
    load_radar_resonance_expanded,
    save_radar_resonance_expanded,
)
from vnpy_common.ui.theme.manager import theme_manager

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

# 兼容旧 import（常量 / 类型仍可从本模块导出）
__all__ = [
    "COLLAPSE_BUTTON_SIZE",
    "RESONANCE_COLLAPSED_WIDTH",
    "RESONANCE_CONTENT_MAX_WIDTH",
    "RESONANCE_CONTENT_MIN_WIDTH",
    "RESONANCE_EXPANDED_DEFAULT_WIDTH",
    "RESONANCE_EXPANDED_MIN_WIDTH",
    "RESONANCE_HANDLE_WIDTH",
    "RadarResonancePanel",
    "RadarResonanceTab",
    "ResonanceFilterMode",
    "resonance_collapse_arrow",
    "sync_radar_resonance_splitter_for_expansion",
]


def resonance_collapse_arrow(expanded: bool) -> QtCore.Qt.ArrowType:
    """左缘按钮：展开时向左收起，折叠时向右展开。"""
    return QtCore.Qt.ArrowType.LeftArrow if expanded else QtCore.Qt.ArrowType.RightArrow


class RadarResonancePanel(QtWidgets.QWidget):
    """全局共振标的汇总侧栏（按统计 / 展望分 Tab）。"""

    expansion_changed = QtCore.Signal(bool)
    row_activated = QtCore.Signal(str)
    row_selected = QtCore.Signal(str)
    add_watchlist_requested = QtCore.Signal(str)
    batch_add_watchlist_requested = QtCore.Signal()
    add_dragon_watchlist_requested = QtCore.Signal()
    stock_analysis_requested = QtCore.Signal(str)
    ai_resonance_requested = QtCore.Signal()
    propose_trading_plan_requested = QtCore.Signal()
    eod_leader_ai_requested = QtCore.Signal()
    open_screener_requested = QtCore.Signal()
    open_leader_screener_requested = QtCore.Signal()
    resonance_weights_requested = QtCore.Signal()
    add_short_term_focus_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RadarResonanceSection")
        self._expanded = load_radar_resonance_expanded()

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        handle = build_resonance_handle(self)
        self._collapse_button = handle.collapse_button
        self._collapse_button.clicked.connect(self._on_collapse_toggled)

        self._body = build_resonance_body()
        header = build_resonance_header()
        tabs = build_resonance_tabs()
        toolbar = build_resonance_toolbar()

        self._count_label = header.count_label
        self._gate_banner = header.gate_banner
        self._risk_banner = header.risk_banner
        self._stats_label = header.stats_label
        self._filter_combo = header.filter_combo
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)

        self._tabs = tabs.tabs
        self._lists = tabs.lists
        self._stacks = tabs.stacks
        self._empty_labels = tabs.empty_labels
        self._row_widgets: dict[RadarResonanceTab, dict[str, RadarResonanceRowWidget]] = {
            key: {} for key, _ in RESONANCE_TABS
        }
        for list_widget in self._lists.values():
            list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._add_all_button = toolbar.add_all_button
        self._dragon_watchlist_button = toolbar.dragon_watchlist_button
        self._focus_button = toolbar.focus_button
        self._ai_button = toolbar.ai_button
        self._screener_button = toolbar.screener_button
        self._leader_button = toolbar.leader_button
        self._weights_button = toolbar.weights_button
        self._plan_button = toolbar.plan_button
        self._eod_button = toolbar.eod_button
        self._wire_toolbar_signals()

        body_layout = QtWidgets.QVBoxLayout(self._body)
        body_layout.setContentsMargins(12, 10, 12, 10)
        body_layout.setSpacing(10)
        body_layout.addLayout(header.layout)
        body_layout.addWidget(self._tabs, stretch=1)
        body_layout.addLayout(toolbar.layout)

        root.addWidget(handle.handle)
        root.addWidget(self._body, stretch=1)

        self._entries_by_tab: dict[RadarResonanceTab, tuple[RadarResonanceEntry, ...]] = {
            key: () for key, _label in RESONANCE_TABS
        }
        self._raw_entries_by_tab: dict[RadarResonanceTab, tuple[RadarResonanceEntry, ...]] = dict(
            self._entries_by_tab
        )
        self._row_lookup: dict[str, object] = {}
        self._filter_mode: ResonanceFilterMode = "all"
        self._emotion_gate_blocked = False
        self._risk_vt_symbols: frozenset[str] = frozenset()
        self._resonance_total = 0
        self._dragon_1_total = 0
        self._ultra_short_count = 0
        self._selected_symbol = ""
        self._sync_action_buttons()
        theme_manager().register_callback(lambda _tokens: self._refresh_list_colors())
        self._apply_expanded(self._expanded, emit=False)

    def _wire_toolbar_signals(self) -> None:
        self._add_all_button.clicked.connect(self.batch_add_watchlist_requested.emit)
        self._dragon_watchlist_button.clicked.connect(self.add_dragon_watchlist_requested.emit)
        self._focus_button.clicked.connect(self.add_short_term_focus_requested.emit)
        self._ai_button.clicked.connect(self.ai_resonance_requested.emit)
        self._screener_button.clicked.connect(self.open_screener_requested.emit)
        self._leader_button.clicked.connect(self.open_leader_screener_requested.emit)
        self._weights_button.clicked.connect(self.resonance_weights_requested.emit)
        self._plan_button.clicked.connect(self.propose_trading_plan_requested.emit)
        self._eod_button.clicked.connect(self.eod_leader_ai_requested.emit)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool, *, emit: bool = True) -> None:
        if self._expanded == expanded:
            return
        self._expanded = expanded
        save_radar_resonance_expanded(expanded)
        self._apply_expanded(expanded, emit=emit)

    def _on_collapse_toggled(self, expanded: bool) -> None:
        self.set_expanded(expanded)

    def _sync_collapse_button(self) -> None:
        self._collapse_button.blockSignals(True)
        self._collapse_button.setChecked(self._expanded)
        self._collapse_button.setArrowType(resonance_collapse_arrow(self._expanded))
        self._collapse_button.setToolTip(collapse_button_tooltip(self._expanded))
        self._collapse_button.blockSignals(False)

    def _apply_expanded(self, expanded: bool, *, emit: bool) -> None:
        self._sync_collapse_button()
        self._body.setVisible(expanded)
        if expanded:
            self.setMinimumWidth(RESONANCE_EXPANDED_MIN_WIDTH)
            self.setMaximumWidth(RESONANCE_HANDLE_WIDTH + RESONANCE_CONTENT_MAX_WIDTH)
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Preferred,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
        else:
            self.setMinimumWidth(RESONANCE_COLLAPSED_WIDTH)
            self.setMaximumWidth(RESONANCE_COLLAPSED_WIDTH)
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Fixed,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
        self.updateGeometry()
        if emit:
            self.expansion_changed.emit(expanded)

    def apply_entries(
        self,
        entries: tuple[RadarResonanceEntry, ...],
        *,
        statistical: tuple[RadarResonanceEntry, ...] | None = None,
        predictive: tuple[RadarResonanceEntry, ...] | None = None,
        allow_new_positions: bool = True,
        emotion_stage_label: str = "",
        row_lookup: dict | None = None,
        resonance_count: int = 0,
        dragon_1_count: int = 0,
        risk_vt_symbols: frozenset[str] | None = None,
    ) -> None:
        self._row_lookup = dict(row_lookup or {})
        self._raw_entries_by_tab = {
            "all": entries,
            "statistical": statistical if statistical is not None else (),
            "predictive": predictive if predictive is not None else (),
        }
        self._emotion_gate_blocked = not allow_new_positions
        self._risk_vt_symbols = risk_vt_symbols or frozenset()
        self._resonance_total = resonance_count
        self._dragon_1_total = dragon_1_count

        gate_text = gate_banner_text(
            blocked=self._emotion_gate_blocked,
            emotion_stage_label=emotion_stage_label,
        )
        if gate_text:
            self._gate_banner.setText(gate_text)
            self._gate_banner.show()
        else:
            self._gate_banner.hide()

        risk_text = risk_banner_text(len(self._risk_vt_symbols))
        if risk_text:
            self._risk_banner.setText(risk_text)
            self._risk_banner.show()
        else:
            self._risk_banner.hide()

        self._apply_filter_to_tabs()
        self._sync_action_buttons()

    def _on_filter_changed(self, _index: int) -> None:
        self._filter_mode = parse_filter_mode(self._filter_combo.currentData())
        self._apply_filter_to_tabs()
        self._sync_action_buttons()

    def _apply_filter_to_tabs(self) -> None:
        self._entries_by_tab, self._ultra_short_count = apply_resonance_filters(
            self._raw_entries_by_tab,
            filter_mode=self._filter_mode,
            row_lookup=self._row_lookup,
            risk_vt_symbols=self._risk_vt_symbols,
        )
        self._stats_label.setText(
            format_resonance_stats(
                resonance_total=self._resonance_total,
                dragon_1_total=self._dragon_1_total,
                ultra_short_count=self._ultra_short_count,
            )
        )
        # 仅重绘当前 Tab；其余 Tab 在切换时由 _on_tab_changed 懒渲染。
        self._render_current_tab()

    def _sync_action_buttons(self) -> None:
        tab_key = self._current_tab_key()
        current = self._entries_by_tab.get(tab_key, ())
        raw_all = self._raw_entries_by_tab.get("all", ())
        state = resonance_action_state(
            has_visible=bool(current),
            has_any_resonance=bool(raw_all),
            blocked=self._emotion_gate_blocked,
            filter_mode=self._filter_mode,
        )
        self._add_all_button.setEnabled(state.add_all_enabled)
        self._dragon_watchlist_button.setEnabled(state.dragon_enabled)
        self._focus_button.setEnabled(state.focus_enabled)
        self._ai_button.setEnabled(state.ai_enabled)
        self._screener_button.setEnabled(state.screener_enabled)
        self._leader_button.setEnabled(state.leader_enabled)
        self._weights_button.setEnabled(state.weights_enabled)
        self._plan_button.setEnabled(state.plan_enabled)
        self._eod_button.setEnabled(state.eod_enabled)
        self._focus_button.setToolTip(state.focus_tooltip)

    def entries(self) -> tuple[RadarResonanceEntry, ...]:
        return self._entries_by_tab.get("all", ())

    def current_tab_entries(self) -> tuple[RadarResonanceEntry, ...]:
        tab_key = self._current_tab_key()
        return self._entries_by_tab.get(tab_key, ())

    def current_tab_key(self) -> RadarResonanceTab:
        return self._current_tab_key()

    def select_tab(self, tab_key: RadarResonanceTab) -> None:
        for index, (key, _label) in enumerate(RESONANCE_TABS):
            if key == tab_key:
                self._tabs.setCurrentIndex(index)
                return

    def _current_tab_key(self) -> RadarResonanceTab:
        index = self._tabs.currentIndex()
        if 0 <= index < len(RESONANCE_TABS):
            return RESONANCE_TABS[index][0]
        return "all"

    def _on_tab_changed(self, _index: int) -> None:
        self._render_current_tab()
        if self._selected_symbol:
            self._sync_row_selection(self._selected_symbol)

    def _render_current_tab(self) -> None:
        tab_key = self._current_tab_key()
        entries = self._entries_by_tab.get(tab_key, ())
        self._count_label.setText(str(len(entries)))
        self._sync_action_buttons()
        self._render_tab(tab_key)

    def _render_tab(self, tab_key: RadarResonanceTab) -> None:
        entries = self._entries_by_tab.get(tab_key, ())
        list_widget = self._lists[tab_key]
        stack = self._stacks[tab_key]
        row_map = self._row_widgets[tab_key]
        list_widget.clear()
        row_map.clear()

        if entries:
            stack.setCurrentIndex(0)
            for entry in entries:
                row = RadarResonanceRowWidget(entry)
                item = QtWidgets.QListWidgetItem()
                item.setData(QtCore.Qt.ItemDataRole.UserRole, entry.vt_symbol)
                row.adjustSize()
                item.setSizeHint(row.sizeHint())
                list_widget.addItem(item)
                list_widget.setItemWidget(item, row)
                row_map[entry.vt_symbol] = row
                vt_symbol = entry.vt_symbol
                row.clicked.connect(lambda sym=vt_symbol: self._select_symbol(sym))
                row.double_clicked.connect(lambda sym=vt_symbol: self.row_activated.emit(sym))
            if tab_key == self._current_tab_key() and self._selected_symbol:
                self._sync_row_selection(self._selected_symbol)
        else:
            stack.setCurrentIndex(1)

    def _sync_row_selection(self, vt_symbol: str) -> None:
        tab_key = self._current_tab_key()
        for symbol, row in self._row_widgets[tab_key].items():
            row.set_selected(symbol == vt_symbol)

    def _select_symbol(self, vt_symbol: str) -> None:
        self._selected_symbol = vt_symbol
        self._sync_row_selection(vt_symbol)
        self.row_selected.emit(vt_symbol)

    def _active_list(self) -> QtWidgets.QListWidget:
        return self._lists[self._current_tab_key()]

    def _refresh_list_colors(self) -> None:
        for row_map in self._row_widgets.values():
            for row in row_map.values():
                row.refresh_theme()

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        list_widget = self._active_list()
        item = list_widget.itemAt(pos)
        if item is None:
            return
        vt_symbol = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not vt_symbol:
            return
        menu = QtWidgets.QMenu(self)
        analysis_action = menu.addAction("个股分析")
        action = menu.addAction("加入自选")
        chosen = menu.exec(list_widget.mapToGlobal(pos))
        if chosen is analysis_action:
            self.stock_analysis_requested.emit(str(vt_symbol))
        elif chosen is action:
            self.add_watchlist_requested.emit(str(vt_symbol))


def sync_radar_resonance_splitter_for_expansion(page: QuotesPage, expanded: bool) -> None:
    """折叠时收窄 splitter 右侧整栏，仅保留左缘折叠钮。"""
    panel = getattr(page, "radar_resonance_panel", None)
    splitter = getattr(page, "_radar_splitter", None)
    if panel is None or splitter is None or splitter.count() < 2:
        return

    if expanded:
        panel.setMinimumWidth(RESONANCE_EXPANDED_MIN_WIDTH)
        panel.setMaximumWidth(RESONANCE_HANDLE_WIDTH + RESONANCE_CONTENT_MAX_WIDTH)
        saved = getattr(page, "_radar_resonance_splitter_saved_state", None)
        if isinstance(saved, QtCore.QByteArray) and not saved.isEmpty():
            splitter.restoreState(saved)
        return

    state = splitter.saveState()
    if isinstance(state, QtCore.QByteArray) and not state.isEmpty():
        page._radar_resonance_splitter_saved_state = state

    panel.setMinimumWidth(RESONANCE_COLLAPSED_WIDTH)
    panel.setMaximumWidth(RESONANCE_COLLAPSED_WIDTH)
    sizes = splitter.sizes()
    total = max(sum(sizes), splitter.width(), RESONANCE_EXPANDED_MIN_WIDTH + 200)
    set_splitter_sizes_quiet(
        splitter,
        [total - RESONANCE_COLLAPSED_WIDTH, RESONANCE_COLLAPSED_WIDTH],
    )
