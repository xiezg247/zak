"""雷达页共振列表侧栏。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.quotes.radar.radar_loaders import RadarResonanceEntry
from vnpy_ashare.ui.components.splitter_utils import set_splitter_sizes_quiet
from vnpy_ashare.ui.quotes.radar.resonance_row_widget import RadarResonanceRowWidget
from vnpy_ashare.ui.quotes.radar.section_prefs import (
    load_radar_resonance_expanded,
    save_radar_resonance_expanded,
)
from vnpy_common.ui.theme.manager import theme_manager

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

RadarResonanceTab = Literal["all", "statistical", "predictive"]
ResonanceFilterMode = Literal["all", "dragon_1", "ultra_short"]

_RESONANCE_TABS: tuple[tuple[RadarResonanceTab, str], ...] = (
    ("all", "全部"),
    ("statistical", "统计"),
    ("predictive", "展望"),
)

RESONANCE_HANDLE_WIDTH = 24
RESONANCE_COLLAPSED_WIDTH = RESONANCE_HANDLE_WIDTH
RESONANCE_CONTENT_MIN_WIDTH = 220
RESONANCE_CONTENT_MAX_WIDTH = 380
RESONANCE_EXPANDED_MIN_WIDTH = RESONANCE_HANDLE_WIDTH + RESONANCE_CONTENT_MIN_WIDTH
RESONANCE_EXPANDED_DEFAULT_WIDTH = 280
COLLAPSE_BUTTON_SIZE = 20


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

        handle = QtWidgets.QWidget(self)
        handle.setObjectName("RadarResonanceHandle")
        handle.setFixedWidth(RESONANCE_HANDLE_WIDTH)
        handle_layout = QtWidgets.QVBoxLayout(handle)
        handle_layout.setContentsMargins(0, 0, 0, 0)
        handle_layout.setSpacing(0)

        self._collapse_button = QtWidgets.QToolButton(handle)
        self._collapse_button.setObjectName("RadarResonanceCollapseButton")
        self._collapse_button.setCheckable(True)
        self._collapse_button.setAutoRaise(True)
        self._collapse_button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._collapse_button.setFixedSize(COLLAPSE_BUTTON_SIZE, COLLAPSE_BUTTON_SIZE)
        self._collapse_button.clicked.connect(self._on_collapse_toggled)

        handle_layout.addStretch(1)
        handle_layout.addWidget(
            self._collapse_button,
            alignment=QtCore.Qt.AlignmentFlag.AlignHCenter,
        )
        handle_layout.addStretch(1)

        self._body = QtWidgets.QFrame(self)
        self._body.setObjectName("RadarResonancePanel")
        self._body.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self._body.setMinimumWidth(RESONANCE_CONTENT_MIN_WIDTH)
        self._body.setMaximumWidth(RESONANCE_CONTENT_MAX_WIDTH)

        header = QtWidgets.QVBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(2)
        title_row = QtWidgets.QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title = QtWidgets.QLabel("共振列表")
        title.setObjectName("RadarResonanceTitle")
        title_row.addWidget(title, stretch=1)
        self._count_label = QtWidgets.QLabel("0")
        self._count_label.setObjectName("RadarResonanceCount")
        title_row.addWidget(self._count_label)
        header.addLayout(title_row)
        hint = QtWidgets.QLabel("多卡同时出现的标的汇总")
        hint.setObjectName("RadarResonanceHint")
        header.addWidget(hint)

        self._gate_banner = QtWidgets.QLabel("")
        self._gate_banner.setObjectName("RadarResonanceGateBanner")
        self._gate_banner.setWordWrap(True)
        self._gate_banner.hide()
        header.addWidget(self._gate_banner)

        self._risk_banner = QtWidgets.QLabel("")
        self._risk_banner.setObjectName("RadarResonanceRiskBanner")
        self._risk_banner.setWordWrap(True)
        self._risk_banner.hide()
        header.addWidget(self._risk_banner)

        self._stats_label = QtWidgets.QLabel("")
        self._stats_label.setObjectName("RadarResonanceStats")
        header.addWidget(self._stats_label)

        filter_row = QtWidgets.QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.addWidget(QtWidgets.QLabel("过滤"))
        self._filter_combo = QtWidgets.QComboBox()
        self._filter_combo.setObjectName("RadarResonanceFilter")
        self._filter_combo.addItem("全部共振", "all")
        self._filter_combo.addItem("仅龙一", "dragon_1")
        self._filter_combo.addItem("短线主池", "ultra_short")
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._filter_combo, stretch=1)
        header.addLayout(filter_row)

        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setObjectName("RadarResonanceTabs")
        self._lists: dict[RadarResonanceTab, QtWidgets.QListWidget] = {}
        self._stacks: dict[RadarResonanceTab, QtWidgets.QStackedWidget] = {}
        self._empty_labels: dict[RadarResonanceTab, QtWidgets.QLabel] = {}
        self._row_widgets: dict[RadarResonanceTab, dict[str, RadarResonanceRowWidget]] = {}
        for tab_key, tab_label in _RESONANCE_TABS:
            page = QtWidgets.QWidget()
            page_layout = QtWidgets.QVBoxLayout(page)
            page_layout.setContentsMargins(0, 4, 0, 0)
            page_layout.setSpacing(0)

            stack = QtWidgets.QStackedWidget()
            list_widget = QtWidgets.QListWidget()
            list_widget.setObjectName("RadarResonanceList")
            list_widget.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
            list_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            list_widget.setSpacing(4)
            list_widget.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
            list_widget.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
            list_widget.customContextMenuRequested.connect(self._show_context_menu)

            empty_page = QtWidgets.QWidget()
            empty_layout = QtWidgets.QVBoxLayout(empty_page)
            empty_layout.setContentsMargins(12, 24, 12, 24)
            empty_label = QtWidgets.QLabel(self._empty_message(tab_key))
            empty_label.setObjectName("RadarResonanceEmpty")
            empty_label.setWordWrap(True)
            empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            empty_layout.addStretch()
            empty_layout.addWidget(empty_label)
            empty_layout.addStretch()

            stack.addWidget(list_widget)
            stack.addWidget(empty_page)
            page_layout.addWidget(stack, stretch=1)

            self._lists[tab_key] = list_widget
            self._stacks[tab_key] = stack
            self._empty_labels[tab_key] = empty_label
            self._row_widgets[tab_key] = {}
            self._tabs.addTab(page, tab_label)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        toolbar = QtWidgets.QGridLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setHorizontalSpacing(6)
        toolbar.setVerticalSpacing(6)
        self._add_all_button = QtWidgets.QPushButton("全部加自选")
        self._add_all_button.setObjectName("RadarResonanceAddAll")
        self._add_all_button.clicked.connect(self.batch_add_watchlist_requested.emit)
        self._dragon_watchlist_button = QtWidgets.QPushButton("龙一入自选")
        self._dragon_watchlist_button.setObjectName("RadarResonanceDragonWatchlist")
        self._dragon_watchlist_button.setToolTip("将 leader_pick 龙一加入自选池")
        self._dragon_watchlist_button.clicked.connect(self.add_dragon_watchlist_requested.emit)
        self._focus_button = QtWidgets.QPushButton("写入短线关注")
        self._focus_button.setObjectName("RadarResonanceShortTermFocus")
        self._focus_button.setToolTip("写入自选池并加入「短线关注」分组")
        self._focus_button.clicked.connect(self.add_short_term_focus_requested.emit)
        self._ai_button = QtWidgets.QPushButton("AI 解读")
        self._ai_button.setObjectName("RadarResonanceAi")
        self._ai_button.clicked.connect(self.ai_resonance_requested.emit)
        self._screener_button = QtWidgets.QPushButton("条件选股")
        self._screener_button.setObjectName("RadarResonanceScreener")
        self._screener_button.clicked.connect(self.open_screener_requested.emit)
        self._leader_button = QtWidgets.QPushButton("龙头选股")
        self._leader_button.setObjectName("RadarResonanceLeader")
        self._leader_button.setToolTip("按 leader_score 执行龙头选股并打开 Hub")
        self._leader_button.clicked.connect(self.open_leader_screener_requested.emit)
        self._weights_button = QtWidgets.QPushButton("权重")
        self._weights_button.setObjectName("RadarResonanceWeights")
        self._weights_button.setToolTip("配置各卡片共振加权分")
        self._weights_button.clicked.connect(self.resonance_weights_requested.emit)
        self._plan_button = QtWidgets.QPushButton("生成次日计划")
        self._plan_button.setObjectName("RadarResonancePlan")
        self._plan_button.setToolTip("基于情绪周期与共振标的生成次日计划草案")
        self._plan_button.clicked.connect(self.propose_trading_plan_requested.emit)
        self._eod_button = QtWidgets.QPushButton("盘后解读")
        self._eod_button.setObjectName("RadarResonanceEod")
        self._eod_button.setToolTip("今日龙头结构 + 明日观察（AI 预填）")
        self._eod_button.clicked.connect(self.eod_leader_ai_requested.emit)
        toolbar.addWidget(self._add_all_button, 0, 0)
        toolbar.addWidget(self._dragon_watchlist_button, 0, 1)
        toolbar.addWidget(self._focus_button, 1, 0, 1, 2)
        toolbar.addWidget(self._ai_button, 2, 0)
        toolbar.addWidget(self._screener_button, 2, 1)
        toolbar.addWidget(self._leader_button, 3, 0)
        toolbar.addWidget(self._weights_button, 3, 1)
        toolbar.addWidget(self._plan_button, 4, 0)
        toolbar.addWidget(self._eod_button, 4, 1)

        body_layout = QtWidgets.QVBoxLayout(self._body)
        body_layout.setContentsMargins(12, 10, 12, 10)
        body_layout.setSpacing(10)
        body_layout.addLayout(header)
        body_layout.addWidget(self._tabs, stretch=1)
        body_layout.addLayout(toolbar)

        root.addWidget(handle)
        root.addWidget(self._body, stretch=1)

        self._entries_by_tab: dict[RadarResonanceTab, tuple[RadarResonanceEntry, ...]] = {key: () for key, _label in _RESONANCE_TABS}
        self._raw_entries_by_tab: dict[RadarResonanceTab, tuple[RadarResonanceEntry, ...]] = dict(self._entries_by_tab)
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
        self._collapse_button.setToolTip("收起共振列表" if self._expanded else "展开共振列表")
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

    @staticmethod
    def _empty_message(tab_key: RadarResonanceTab) -> str:
        if tab_key == "statistical":
            return "暂无统计区共振\n需同时出现在 2 张及以上统计卡"
        if tab_key == "predictive":
            return "暂无展望区共振\n需同时出现在 2 张及以上展望卡"
        return "暂无共振标的\n需同时出现在 2 张及以上卡片"

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
        if self._emotion_gate_blocked and emotion_stage_label:
            self._gate_banner.setText(f"{emotion_stage_label}：不宜短线新开仓")
            self._gate_banner.show()
        else:
            self._gate_banner.hide()
        if self._risk_vt_symbols:
            self._risk_banner.setText(f"炸板断板风险 {len(self._risk_vt_symbols)} 只（主池过滤已剔除）")
            self._risk_banner.show()
        else:
            self._risk_banner.hide()
        self._apply_filter_to_tabs()
        self._sync_action_buttons()

    def _on_filter_changed(self, _index: int) -> None:
        mode = self._filter_combo.currentData()
        if mode in ("all", "dragon_1", "ultra_short"):
            self._filter_mode = mode
        self._apply_filter_to_tabs()
        self._sync_action_buttons()

    def _apply_filter_to_tabs(self) -> None:
        from vnpy_ashare.quotes.radar.radar_snapshot import resonance_entry_to_row_dict
        from vnpy_ashare.screener.run.ultra_short_pool_filter import filter_resonance_entries

        lookup = {
            vt: resonance_entry_to_row_dict(entry, self._row_lookup)  # type: ignore[arg-type]
            for vt, entry in ((e.vt_symbol, e) for tab in self._raw_entries_by_tab.values() for e in tab)
        }
        self._ultra_short_count = len(
            [
                entry
                for entry in filter_resonance_entries(
                    self._raw_entries_by_tab.get("all", ()),
                    mode="ultra_short",
                    row_lookup=lookup,
                )
                if entry.vt_symbol not in self._risk_vt_symbols
            ]
        )
        risk = self._risk_vt_symbols

        def _filter_entries(raw: tuple[RadarResonanceEntry, ...]) -> tuple[RadarResonanceEntry, ...]:
            filtered = tuple(filter_resonance_entries(raw, mode=self._filter_mode, row_lookup=lookup))
            if self._filter_mode == "ultra_short" and risk:
                filtered = tuple(entry for entry in filtered if entry.vt_symbol not in risk)
            return filtered

        self._stats_label.setText(f"共振 {self._resonance_total} · 龙一 {self._dragon_1_total} · 主池 {self._ultra_short_count}")
        for tab_key, raw in self._raw_entries_by_tab.items():
            self._entries_by_tab[tab_key] = _filter_entries(raw)
        # 仅重绘当前 Tab；其余 Tab 在切换时由 _on_tab_changed 懒渲染，避免共振同步时主线程拥堵。
        self._render_current_tab()

    def _sync_action_buttons(self) -> None:
        """同步侧栏操作按钮可用态与提示。"""
        tab_key = self._current_tab_key()
        current = self._entries_by_tab.get(tab_key, ())
        raw_all = self._raw_entries_by_tab.get("all", ())
        has_visible = bool(current)
        has_any_resonance = bool(raw_all)
        blocked = self._emotion_gate_blocked

        self._add_all_button.setEnabled(has_visible)
        self._dragon_watchlist_button.setEnabled(has_visible and not blocked)
        # 短线关注为观察池，退潮期仍允许写入（与龙头选股 gate 区分）
        self._focus_button.setEnabled(has_visible)
        self._ai_button.setEnabled(has_visible)
        self._screener_button.setEnabled(has_visible)
        self._leader_button.setEnabled(has_visible and not blocked)
        self._weights_button.setEnabled(True)
        self._plan_button.setEnabled(True)
        self._eod_button.setEnabled(True)

        if not has_visible:
            if has_any_resonance and self._filter_mode != "all":
                self._focus_button.setToolTip("当前过滤下无标的：可切回「全部共振」或放宽过滤后再写入")
            elif not has_any_resonance:
                self._focus_button.setToolTip("暂无共振标的（需同时出现在 2 张及以上卡片）。请先刷新雷达卡片")
            else:
                self._focus_button.setToolTip("当前 Tab 下无共振标的")
        else:
            tip = "将当前列表写入自选池并加入「短线关注」分组（追加，不覆盖）"
            if blocked:
                tip += "。注：情绪退潮期仍可建观察池，不宜新开仓"
            self._focus_button.setToolTip(tip)

    def entries(self) -> tuple[RadarResonanceEntry, ...]:
        return self._entries_by_tab.get("all", ())

    def current_tab_entries(self) -> tuple[RadarResonanceEntry, ...]:
        tab_key = self._current_tab_key()
        return self._entries_by_tab.get(tab_key, ())

    def current_tab_key(self) -> RadarResonanceTab:
        return self._current_tab_key()

    def select_tab(self, tab_key: RadarResonanceTab) -> None:
        for index, (key, _label) in enumerate(_RESONANCE_TABS):
            if key == tab_key:
                self._tabs.setCurrentIndex(index)
                return

    def _current_tab_key(self) -> RadarResonanceTab:
        index = self._tabs.currentIndex()
        if 0 <= index < len(_RESONANCE_TABS):
            return _RESONANCE_TABS[index][0]
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
