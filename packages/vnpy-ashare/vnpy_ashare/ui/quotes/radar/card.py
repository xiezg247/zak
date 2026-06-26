"""雷达页卡片 UI。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.time.market_hours import ashare_market_phase, ashare_market_phase_label
from vnpy_ashare.quotes.market.emotion_cycle_subtitle import append_emotion_cycle_to_subtitle
from vnpy_ashare.quotes.radar.outlook_strategy_prefs import (
    load_outlook_strategy_class,
    outlook_strategy_options,
)
from vnpy_ashare.quotes.radar.radar_catalog import (
    RADAR_GRID_COLUMNS,
    RADAR_LAYOUT_SECTIONS,
    RadarCardMode,
    RadarCardSpec,
    RadarGroupKey,
    default_refresh_ms_for_card,
    default_variant_for_card,
    full_refresh_options_for_card,
    list_radar_cards_for_group,
    list_radar_groups_for_mode,
    radar_card_group,
    refresh_options_for_card,
    supports_auto_refresh,
    variants_for_card,
)
from vnpy_ashare.quotes.radar.radar_full_refresh_prefs import load_radar_full_refresh_every
from vnpy_ashare.quotes.radar.loaders import RadarCardData, RadarRow, compute_radar_resonance
from vnpy_ashare.ui.quotes.page.config import load_radar_card_refresh_ms
from vnpy_ashare.ui.quotes.radar.row_widget import RadarStockRowWidget
from vnpy_ashare.ui.quotes.radar.section_prefs import (
    load_radar_board_group,
    load_radar_board_mode,
    save_radar_board_group,
    save_radar_board_mode,
)
from vnpy_common.ui.panel_widgets import configure_document_tab_widget
from vnpy_common.ui.theme.manager import theme_manager

_BODY_PAGE_ROWS = 0
_BODY_PAGE_EMPTY = 1

_RADAR_ROW_LAYOUT_HEIGHT = 34
_RADAR_ROW_SPACING = 3
_RADAR_CARD_CHROME_HEIGHT = 108


def _estimate_card_min_height(top_n: int) -> int:
    """按展示条数估算卡片最小高度，避免列表区被压扁。"""
    rows = max(1, int(top_n))
    body = rows * _RADAR_ROW_LAYOUT_HEIGHT + max(0, rows - 1) * _RADAR_ROW_SPACING
    return _RADAR_CARD_CHROME_HEIGHT + body


class RadarCardWidget(QtWidgets.QFrame):
    """单张雷达卡片。"""

    variant_changed = QtCore.Signal(str)
    row_activated = QtCore.Signal(str)
    row_selected = QtCore.Signal(str)
    add_watchlist_requested = QtCore.Signal(str)
    batch_add_watchlist_requested = QtCore.Signal(str)
    stock_analysis_requested = QtCore.Signal(str)
    view_run_requested = QtCore.Signal(str, str)
    sector_flow_requested = QtCore.Signal(str)
    sector_rotation_requested = QtCore.Signal(str)
    refresh_requested = QtCore.Signal(str)
    quote_refresh_requested = QtCore.Signal(str)
    ai_requested = QtCore.Signal(str)
    auto_refresh_changed = QtCore.Signal(str, int)
    full_refresh_interval_changed = QtCore.Signal(str, int)

    def __init__(self, spec: RadarCardSpec, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._spec = spec
        self._supports_auto_refresh = supports_auto_refresh(spec.id)
        if spec.mode == "predictive":
            object_name = "RadarCardPredictive"
        elif self._supports_auto_refresh:
            object_name = "RadarCardLive"
        else:
            object_name = "RadarCardManual"
        self.setObjectName(object_name)
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        self.setMinimumHeight(_estimate_card_min_height(spec.top_n))

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)
        header.setContentsMargins(0, 0, 0, 0)
        self._title = QtWidgets.QLabel(spec.title)
        self._title.setObjectName("RadarCardTitle")
        header.addWidget(
            self._title,
            stretch=1,
            alignment=QtCore.Qt.AlignmentFlag.AlignVCenter,
        )

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(6)
        actions.setContentsMargins(0, 0, 0, 0)

        badge_group = QtWidgets.QWidget()
        badge_group.setObjectName("RadarCardBadgeGroup")
        badge_layout = QtWidgets.QHBoxLayout(badge_group)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.setSpacing(4)

        self._kind_badge = QtWidgets.QLabel("统计" if spec.mode == "statistical" else "展望")
        self._kind_badge.setObjectName("RadarCardKindBadgeStatistical" if spec.mode == "statistical" else "RadarCardKindBadgePredictive")
        badge_layout.addWidget(self._kind_badge)

        self._mode_badge = QtWidgets.QLabel("")
        self._mode_badge.setObjectName("RadarCardModeBadge")
        self._update_mode_badge()
        badge_layout.addWidget(self._mode_badge)
        actions.addWidget(badge_group)

        self._variant_combo = QtWidgets.QComboBox()
        self._variant_combo.setObjectName("RadarCardVariant")
        if spec.has_task_variants:
            for variant in variants_for_card(spec.id):
                self._variant_combo.addItem(variant.label, variant.key)
            default_key = default_variant_for_card(spec.id)
            if default_key:
                self.set_variant_key(default_key)
            self._variant_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self._variant_combo.setMinimumContentsLength(5)
            self._variant_combo.setMaximumWidth(108)
            self._variant_combo.currentIndexChanged.connect(self._emit_variant_changed)
            actions.addWidget(self._variant_combo)
        else:
            self._variant_combo.hide()

        self._refresh_interval_combo = QtWidgets.QComboBox()
        self._refresh_interval_combo.setObjectName("RadarCardRefreshInterval")
        self._refresh_interval_combo.setToolTip("自动刷新周期")
        refresh_options = refresh_options_for_card(spec.id)
        if refresh_options:
            for option in refresh_options:
                self._refresh_interval_combo.addItem(option.label, option.ms)
            default_ms = load_radar_card_refresh_ms(spec.id, default_refresh_ms_for_card(spec.id))
            self.set_auto_refresh_ms(default_ms)
            self._refresh_interval_combo.currentIndexChanged.connect(self._emit_auto_refresh_changed)
            actions.addWidget(self._refresh_interval_combo)
        else:
            self._refresh_interval_combo.hide()

        self._full_refresh_combo = QtWidgets.QComboBox()
        self._full_refresh_combo.setObjectName("RadarCardFullRefreshInterval")
        self._full_refresh_combo.setToolTip("自动刷新时，每隔多少次全量重算指标（其余仅更新现价 / 涨幅）")
        full_refresh_options = full_refresh_options_for_card(spec.id)
        if full_refresh_options:
            for option in full_refresh_options:
                self._full_refresh_combo.addItem(option.label, option.ms)
            default_every = load_radar_full_refresh_every(spec.id)
            self.set_full_refresh_every(default_every)
            self._full_refresh_combo.currentIndexChanged.connect(self._emit_full_refresh_interval_changed)
            actions.addWidget(self._full_refresh_combo)
        else:
            self._full_refresh_combo.hide()

        self._refresh_button = QtWidgets.QToolButton()
        self._refresh_button.setObjectName("RadarCardRefresh")
        self._refresh_button.setText("↻")
        self._refresh_button.setToolTip("全量刷新")
        self._refresh_button.clicked.connect(lambda: self.refresh_requested.emit(self.card_id))

        self._refresh_menu_button = QtWidgets.QToolButton()
        self._refresh_menu_button.setObjectName("RadarCardRefreshMenu")
        self._refresh_menu_button.setText("▾")
        self._refresh_menu_button.setToolTip("更多刷新选项")
        self._refresh_menu_button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        refresh_menu = QtWidgets.QMenu(self._refresh_menu_button)
        refresh_menu.addAction("全量刷新", lambda: self.refresh_requested.emit(self.card_id))
        refresh_menu.addAction("仅更新行情", lambda: self.quote_refresh_requested.emit(self.card_id))
        self._refresh_menu_button.setMenu(refresh_menu)

        refresh_group = QtWidgets.QWidget()
        refresh_group.setObjectName("RadarCardRefreshGroup")
        refresh_layout = QtWidgets.QHBoxLayout(refresh_group)
        refresh_layout.setContentsMargins(0, 0, 0, 0)
        refresh_layout.setSpacing(4)
        refresh_layout.addWidget(self._refresh_button)
        refresh_layout.addWidget(self._refresh_menu_button)

        header_divider = QtWidgets.QWidget()
        header_divider.setObjectName("RadarCardHeaderDivider")
        header_divider.setFixedSize(1, 14)
        actions.addWidget(header_divider)
        actions.addWidget(refresh_group)

        actions_host = QtWidgets.QWidget()
        actions_host.setObjectName("RadarCardHeaderActions")
        actions_host.setLayout(actions)
        header.addWidget(
            actions_host,
            alignment=QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight,
        )

        self._subtitle = QtWidgets.QLabel("")
        self._subtitle.setObjectName("RadarCardSubtitle")
        self._subtitle.setWordWrap(True)
        self._subtitle.setMaximumHeight(30)
        self._subtitle.setMinimumHeight(0)

        self._ai_hint = QtWidgets.QLabel("")
        self._ai_hint.setObjectName("RadarCardAiHint")
        self._ai_hint.setWordWrap(True)
        self._ai_hint.hide()

        self._rows_host = QtWidgets.QWidget()
        self._rows_host.setObjectName("RadarCardRowsHost")
        self._rows_layout = QtWidgets.QVBoxLayout(self._rows_host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(_RADAR_ROW_SPACING)

        self._rows_page = QtWidgets.QWidget()
        self._rows_page.setObjectName("RadarCardRowsPage")
        rows_page_layout = QtWidgets.QVBoxLayout(self._rows_page)
        rows_page_layout.setContentsMargins(0, 0, 0, 0)
        rows_page_layout.setSpacing(0)
        rows_page_layout.addWidget(self._rows_host)

        self._empty_label = QtWidgets.QLabel("")
        self._empty_label.setObjectName("RadarCardEmpty")
        self._empty_label.setWordWrap(True)
        self._empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self._empty_page = QtWidgets.QWidget()
        self._empty_page.setObjectName("RadarCardEmptyPage")
        empty_page_layout = QtWidgets.QVBoxLayout(self._empty_page)
        empty_page_layout.setContentsMargins(0, 0, 0, 0)
        empty_page_layout.addStretch(1)
        empty_page_layout.addWidget(self._empty_label)
        empty_page_layout.addStretch(1)

        self._body_stack = QtWidgets.QStackedWidget()
        self._body_stack.setObjectName("RadarCardBodyStack")
        self._body_stack.addWidget(self._rows_page)
        self._body_stack.addWidget(self._empty_page)
        self._body_stack.setCurrentIndex(_BODY_PAGE_ROWS)
        self._body_stack.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )

        footer = QtWidgets.QHBoxLayout()
        footer.setSpacing(8)
        self._meta_label = QtWidgets.QLabel("")
        self._meta_label.setObjectName("RadarCardMeta")
        footer.addWidget(self._meta_label, stretch=1)
        self._ai_button = QtWidgets.QPushButton("AI")
        self._ai_button.setObjectName("RadarCardAi")
        self._ai_button.setFlat(True)
        self._ai_button.setToolTip("解读本卡片")
        self._ai_button.clicked.connect(lambda: self.ai_requested.emit(self.card_id))
        footer.addWidget(self._ai_button)
        self._view_run_button = QtWidgets.QPushButton("查看完整")
        self._view_run_button.setObjectName("RadarCardViewRun")
        self._view_run_button.setFlat(True)
        self._view_run_button.hide()
        self._view_run_button.clicked.connect(self._on_view_run_clicked)
        footer.addWidget(self._view_run_button)
        self._sector_flow_button: QtWidgets.QPushButton | None = None
        self._sector_rotation_button: QtWidgets.QPushButton | None = None
        if spec.id in ("sector_theme", "sector_flow_hot"):
            self._sector_flow_button = QtWidgets.QPushButton("板块资金")
            self._sector_flow_button.setObjectName("RadarCardSectorFlow")
            self._sector_flow_button.setFlat(True)
            self._sector_flow_button.setToolTip("打开板块资金监控页并预选主线行业")
            self._sector_flow_button.clicked.connect(lambda: self.sector_flow_requested.emit(self.card_id))
            footer.addWidget(self._sector_flow_button)
            self._sector_rotation_button = QtWidgets.QPushButton("近15日轮动")
            self._sector_rotation_button.setObjectName("RadarCardSectorRotation")
            self._sector_rotation_button.setFlat(True)
            self._sector_rotation_button.setToolTip("打开板块资金页近15日轮动矩阵并预选主线行业")
            self._sector_rotation_button.clicked.connect(lambda: self.sector_rotation_requested.emit(self.card_id))
            footer.addWidget(self._sector_rotation_button)
        else:
            self._sector_flow_button = None
            self._sector_rotation_button = None
        self._add_all_button = QtWidgets.QPushButton("全部加自选")
        self._add_all_button.setObjectName("RadarCardAddAll")
        self._add_all_button.setFlat(True)
        self._add_all_button.hide()
        self._add_all_button.clicked.connect(self._on_add_all_clicked)
        footer.addWidget(self._add_all_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        layout.addLayout(header)
        layout.addWidget(self._subtitle)
        layout.addWidget(self._ai_hint)
        layout.addWidget(self._body_stack)
        layout.addLayout(footer)

        self._run_id = ""
        self._detail_page_key = ""
        self._sector_names: tuple[str, ...] = ()
        self._resonance_counts: dict[str, int] = {}
        self._loading = False
        self._updated_at_text = ""
        self._row_widgets: list[RadarStockRowWidget] = []
        self._show_add_watchlist_actions = spec.id != "watchlist_intraday"

        theme_manager().register_callback(lambda _tokens: self._refresh_row_widgets())

    @property
    def card_id(self) -> str:
        return self._spec.id

    def set_variant_key(self, key: str) -> None:
        if not self._spec.has_task_variants:
            return
        index = self._variant_combo.findData(key)
        if index >= 0:
            self._variant_combo.blockSignals(True)
            self._variant_combo.setCurrentIndex(index)
            self._variant_combo.blockSignals(False)

    def variant_key(self) -> str:
        if not self._spec.has_task_variants:
            return ""
        value = self._variant_combo.currentData()
        return str(value or "")

    def auto_refresh_ms(self) -> int:
        if not self._supports_auto_refresh:
            return 0
        value = self._refresh_interval_combo.currentData()
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def set_auto_refresh_ms(self, ms: int) -> None:
        if not self._supports_auto_refresh:
            return
        index = self._refresh_interval_combo.findData(int(ms))
        if index < 0:
            index = self._refresh_interval_combo.findData(default_refresh_ms_for_card(self.card_id))
        if index >= 0:
            self._refresh_interval_combo.blockSignals(True)
            self._refresh_interval_combo.setCurrentIndex(index)
            self._refresh_interval_combo.blockSignals(False)

    def full_refresh_every(self) -> int:
        if not self._supports_auto_refresh:
            return 1
        value = self._full_refresh_combo.currentData()
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return 1

    def set_full_refresh_every(self, every_n: int) -> None:
        if not self._supports_auto_refresh:
            return
        index = self._full_refresh_combo.findData(int(every_n))
        if index < 0:
            index = self._full_refresh_combo.findData(load_radar_full_refresh_every(self.card_id))
        if index >= 0:
            self._full_refresh_combo.blockSignals(True)
            self._full_refresh_combo.setCurrentIndex(index)
            self._full_refresh_combo.blockSignals(False)

    def update_mode_badge(self) -> None:
        self._update_mode_badge()

    def _update_mode_badge(self) -> None:
        if not self._supports_auto_refresh:
            self._mode_badge.setText("手动")
            self._mode_badge.setObjectName("RadarCardModeBadgeOff")
        else:
            phase = ashare_market_phase()
            self._mode_badge.setText(ashare_market_phase_label())
            self._mode_badge.setObjectName("RadarCardModeBadgeLive" if phase == "intraday" else "RadarCardModeBadgeOff")
        style = self._mode_badge.style()
        style.unpolish(self._mode_badge)
        style.polish(self._mode_badge)

    def sector_names(self) -> list[str]:
        return list(self._sector_names)

    def set_loading(self, loading: bool) -> None:
        self._loading = loading
        self._refresh_button.setEnabled(not loading)
        self._refresh_menu_button.setEnabled(not loading)
        if loading:
            self._meta_label.setText("加载中…")
            return
        if self._row_widgets or self._updated_at_text:
            card_resonance = sum(1 for widget in self._row_widgets if widget.vt_symbol() and self._resonance_counts.get(widget.vt_symbol(), 0) >= 2)
            self._apply_meta_label_from_resonance(card_resonance)
        else:
            self._meta_label.setText("")

    def _clear_row_widgets(self) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._row_widgets.clear()

    def apply_data(self, data: RadarCardData, *, resonance_counts: dict[str, int] | None = None) -> None:
        self._loading = False
        self._refresh_button.setEnabled(True)
        self._refresh_menu_button.setEnabled(True)
        self._subtitle.setText(
            append_emotion_cycle_to_subtitle(data.subtitle) if data.card_id.startswith(("discovery_", "leader_", "sector_")) else data.subtitle,
        )
        hint = str(data.ai_hint or "").strip()
        if hint:
            self._ai_hint.setText(hint)
            self._ai_hint.show()
        else:
            self._ai_hint.hide()
            self._ai_hint.setText("")
        self._run_id = data.run_id
        self._detail_page_key = data.detail_page_key
        self._sector_names = tuple(data.sector_names)
        self._resonance_counts = dict(resonance_counts or {})
        if data.run_id and data.detail_page_key:
            self._view_run_button.show()
        else:
            self._view_run_button.hide()
        if data.rows and self._show_add_watchlist_actions:
            self._add_all_button.show()
        else:
            self._add_all_button.hide()
        self._apply_meta_label(data)
        new_symbols = tuple(row.vt_symbol for row in data.rows)
        old_symbols = tuple(widget.vt_symbol() for widget in self._row_widgets)
        if data.rows and new_symbols == old_symbols:
            self._body_stack.setCurrentIndex(_BODY_PAGE_ROWS)
            quote_by_vt = {row.vt_symbol: row for row in data.rows}
            for widget in self._row_widgets:
                row = quote_by_vt.get(widget.vt_symbol())
                if row is not None:
                    widget.refresh_row(row)
                    widget.update_resonance(self._resonance_counts.get(row.vt_symbol, 0))
            return
        self._clear_row_widgets()
        if data.rows:
            self._body_stack.setCurrentIndex(_BODY_PAGE_ROWS)
            for row in data.rows:
                resonance = self._resonance_counts.get(row.vt_symbol, 0)
                widget = RadarStockRowWidget(
                    row,
                    resonance=resonance,
                    show_add_watchlist_action=self._show_add_watchlist_actions,
                    parent=self._rows_host,
                )
                widget.clicked.connect(self.row_selected.emit)
                widget.double_clicked.connect(self.row_activated.emit)
                widget.add_watchlist_requested.connect(self.add_watchlist_requested.emit)
                widget.stock_analysis_requested.connect(self.stock_analysis_requested.emit)
                self._rows_layout.addWidget(widget)
                self._row_widgets.append(widget)
            return
        self._empty_label.setText(data.empty_message or "暂无数据")
        self._body_stack.setCurrentIndex(_BODY_PAGE_EMPTY)

    def update_resonance(self, resonance_counts: dict[str, int]) -> None:
        """仅更新共振标记，不重新加载卡片数据。"""
        if self._loading:
            return
        self._resonance_counts = dict(resonance_counts)
        card_resonance = 0
        for widget in self._row_widgets:
            resonance = self._resonance_counts.get(widget.vt_symbol(), 0)
            widget.update_resonance(resonance)
            if resonance >= 2:
                card_resonance += 1
        self._apply_meta_label_from_resonance(card_resonance)

    def apply_quote_update(self, rows: tuple[RadarRow, ...]) -> None:
        """增量更新现价 / 涨幅，不重建行组件。"""
        if self._loading or not self._row_widgets:
            return
        quote_by_vt = {row.vt_symbol: row for row in rows}
        for widget in self._row_widgets:
            row = quote_by_vt.get(widget.vt_symbol())
            if row is None:
                continue
            widget.update_quotes(row.price, row.change_pct)

    def _apply_meta_label(self, data: RadarCardData) -> None:
        self._updated_at_text = f"更新 {data.updated_at}" if data.updated_at else ""
        card_resonance = sum(1 for row in data.rows if self._resonance_counts.get(row.vt_symbol, 0) >= 2)
        self._apply_meta_label_from_resonance(card_resonance)

    def _apply_meta_label_from_resonance(self, card_resonance: int) -> None:
        meta_parts: list[str] = []
        if self._updated_at_text:
            meta_parts.append(self._updated_at_text)
        if card_resonance:
            meta_parts.append(f"共振 {card_resonance}")
        self._meta_label.setText(" · ".join(meta_parts))

    def _refresh_row_widgets(self) -> None:
        for widget in self._row_widgets:
            widget.refresh_theme()

    def _on_add_all_clicked(self) -> None:
        self.batch_add_watchlist_requested.emit(self.card_id)

    def _emit_variant_changed(self, _index: int) -> None:
        key = self.variant_key()
        if key:
            self.variant_changed.emit(key)

    def _emit_auto_refresh_changed(self, _index: int) -> None:
        self.auto_refresh_changed.emit(self.card_id, self.auto_refresh_ms())

    def _emit_full_refresh_interval_changed(self, _index: int) -> None:
        self.full_refresh_interval_changed.emit(self.card_id, self.full_refresh_every())

    def _on_view_run_clicked(self) -> None:
        if self._run_id and self._detail_page_key:
            self.view_run_requested.emit(self._run_id, self._detail_page_key)


class RadarBoard(QtWidgets.QWidget):
    """雷达卡片分区布局：盘面统计 / 前瞻展望 Tab。"""

    variant_changed = QtCore.Signal(str, str)
    row_activated = QtCore.Signal(str)
    row_selected = QtCore.Signal(str)
    add_watchlist_requested = QtCore.Signal(str)
    batch_add_watchlist_requested = QtCore.Signal(str)
    stock_analysis_requested = QtCore.Signal(str)
    view_run_requested = QtCore.Signal(str, str)
    sector_flow_requested = QtCore.Signal(str)
    sector_rotation_requested = QtCore.Signal(str)
    refresh_requested = QtCore.Signal(str)
    quote_refresh_requested = QtCore.Signal(str)
    ai_requested = QtCore.Signal(str)
    auto_refresh_changed = QtCore.Signal(str, int)
    full_refresh_interval_changed = QtCore.Signal(str, int)
    mode_changed = QtCore.Signal(str)
    group_changed = QtCore.Signal(str, str)
    outlook_strategy_changed = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RadarBoard")

        self._cards: dict[str, RadarCardWidget] = {}
        self._mode_tab_index: dict[RadarCardMode, int] = {}
        self._group_tabs: dict[RadarCardMode, QtWidgets.QTabWidget] = {}
        self._group_index: dict[RadarCardMode, dict[int, RadarGroupKey]] = {}
        self._group_scrolls: dict[tuple[RadarCardMode, RadarGroupKey], QtWidgets.QScrollArea] = {}
        self._outlook_strategy_combo: QtWidgets.QComboBox | None = None

        self._tabs = configure_document_tab_widget(
            QtWidgets.QTabWidget(),
            object_name="RadarBoardTabs",
        )

        columns = RADAR_GRID_COLUMNS
        for section_index, section in enumerate(RADAR_LAYOUT_SECTIONS):
            page = QtWidgets.QWidget()
            page.setObjectName(f"RadarBoardTab{section.mode.title()}")
            page_layout = QtWidgets.QVBoxLayout(page)
            page_layout.setContentsMargins(8, 8, 8, 8)
            page_layout.setSpacing(8)

            if section.mode == "predictive":
                toolbar = QtWidgets.QHBoxLayout()
                toolbar.setSpacing(8)
                toolbar_label = QtWidgets.QLabel("展望策略")
                toolbar_label.setObjectName("RadarOutlookStrategyLabel")
                toolbar.addWidget(toolbar_label)
                strategy_combo = QtWidgets.QComboBox()
                strategy_combo.setObjectName("RadarOutlookStrategyCombo")
                strategy_combo.setToolTip("前瞻展望区全市场扫描使用的信号策略（与自选信号区独立）")
                for option in outlook_strategy_options():
                    strategy_combo.addItem(option.label, option.class_name)
                default_class = load_outlook_strategy_class()
                default_index = strategy_combo.findData(default_class)
                if default_index >= 0:
                    strategy_combo.setCurrentIndex(default_index)
                strategy_combo.currentIndexChanged.connect(self._emit_outlook_strategy_changed)
                toolbar.addWidget(strategy_combo)
                toolbar.addStretch(1)
                page_layout.addLayout(toolbar)
                self._outlook_strategy_combo = strategy_combo

            group_tabs = configure_document_tab_widget(
                QtWidgets.QTabWidget(),
                object_name=f"RadarBoardGroupTabs{section.mode.title()}",
            )
            index_map: dict[int, RadarGroupKey] = {}
            for group_index, (group_key, group_label) in enumerate(list_radar_groups_for_mode(section.mode)):
                group_page = QtWidgets.QWidget()
                group_layout = QtWidgets.QVBoxLayout(group_page)
                group_layout.setContentsMargins(0, 4, 0, 0)
                group_layout.setSpacing(0)

                scroll = QtWidgets.QScrollArea()
                scroll.setObjectName("RadarBoardScroll")
                scroll.setWidgetResizable(True)
                scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
                scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

                section_host = QtWidgets.QWidget()
                section_host.setObjectName(f"RadarSectionGrid{section.mode.title()}{group_key.title()}")
                grid = QtWidgets.QGridLayout(section_host)
                grid.setContentsMargins(0, 0, 0, 0)
                grid.setSpacing(10)

                specs = list_radar_cards_for_group(section.mode, group_key)
                for index, spec in enumerate(specs):
                    card = self._wire_card(spec)
                    grid.addWidget(
                        card,
                        index // columns,
                        index % columns,
                        QtCore.Qt.AlignmentFlag.AlignTop,
                    )

                for col in range(columns):
                    grid.setColumnStretch(col, 1)

                scroll.setWidget(section_host)
                group_layout.addWidget(scroll, stretch=1)
                self._group_scrolls[(section.mode, group_key)] = scroll
                group_tabs.addTab(group_page, group_label)
                index_map[group_index] = group_key

            self._group_tabs[section.mode] = group_tabs
            self._group_index[section.mode] = index_map
            group_tabs.currentChanged.connect(
                lambda index, mode=section.mode: self._on_group_tab_changed(mode, index),
            )
            page_layout.addWidget(group_tabs, stretch=1)

            self._tabs.addTab(page, section.title)
            self._tabs.setTabToolTip(section_index, section.hint)
            self._mode_tab_index[section.mode] = section_index

        self._tabs.currentChanged.connect(self._on_tab_changed)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._tabs)

        self.set_mode(load_radar_board_mode(), persist=False)
        for section in RADAR_LAYOUT_SECTIONS:
            self.set_group(section.mode, load_radar_board_group(section.mode), persist=False)
        self.update_tab_badges()

    def current_mode(self) -> RadarCardMode:
        index = self._tabs.currentIndex()
        if 0 <= index < len(RADAR_LAYOUT_SECTIONS):
            return RADAR_LAYOUT_SECTIONS[index].mode
        return "statistical"

    def set_mode(self, mode: RadarCardMode, *, persist: bool = True) -> None:
        tab_index = self._mode_tab_index.get(mode)
        if tab_index is None:
            return
        self._tabs.blockSignals(True)
        self._tabs.setCurrentIndex(tab_index)
        self._tabs.blockSignals(False)
        if persist:
            save_radar_board_mode(mode)

    def current_group(self, mode: RadarCardMode | None = None) -> RadarGroupKey:
        active_mode = mode or self.current_mode()
        tabs = self._group_tabs.get(active_mode)
        index_map = self._group_index.get(active_mode, {})
        if tabs is None:
            from vnpy_ashare.quotes.radar.radar_catalog import default_group_for_mode

            return default_group_for_mode(active_mode)
        index = tabs.currentIndex()
        return index_map.get(index, load_radar_board_group(active_mode))

    def set_group(self, mode: RadarCardMode, group_key: RadarGroupKey, *, persist: bool = True) -> None:
        tabs = self._group_tabs.get(mode)
        index_map = self._group_index.get(mode, {})
        if tabs is None:
            return
        target_index = next((idx for idx, key in index_map.items() if key == group_key), None)
        if target_index is None:
            return
        tabs.blockSignals(True)
        tabs.setCurrentIndex(target_index)
        tabs.blockSignals(False)
        if persist:
            save_radar_board_group(mode, group_key)

    def update_tab_badges(self) -> None:
        for section_index, section in enumerate(RADAR_LAYOUT_SECTIONS):
            self._tabs.setTabText(section_index, section.title)
            self._tabs.setTabToolTip(section_index, section.hint)

    def outlook_strategy_class(self) -> str:
        combo = self._outlook_strategy_combo
        if combo is None:
            return load_outlook_strategy_class()
        value = combo.currentData()
        return str(value or load_outlook_strategy_class())

    def set_outlook_strategy_class(self, class_name: str) -> None:
        combo = self._outlook_strategy_combo
        if combo is None:
            return
        index = combo.findData(class_name)
        if index < 0:
            return
        combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _emit_outlook_strategy_changed(self, _index: int) -> None:
        class_name = self.outlook_strategy_class()
        if class_name:
            self.outlook_strategy_changed.emit(class_name)

    def _on_tab_changed(self, index: int) -> None:
        if index < 0 or index >= len(RADAR_LAYOUT_SECTIONS):
            return
        mode = RADAR_LAYOUT_SECTIONS[index].mode
        save_radar_board_mode(mode)
        self.mode_changed.emit(mode)

    def _on_group_tab_changed(self, mode: RadarCardMode, index: int) -> None:
        group_key = self._group_index.get(mode, {}).get(index)
        if group_key is None:
            return
        save_radar_board_group(mode, group_key)
        self.group_changed.emit(mode, group_key)

    def _wire_card(self, spec: RadarCardSpec) -> RadarCardWidget:
        card = RadarCardWidget(spec, self)
        card.setMinimumHeight(_estimate_card_min_height(spec.top_n))
        card.variant_changed.connect(lambda key, card_id=spec.id: self.variant_changed.emit(card_id, key))
        card.row_activated.connect(self.row_activated.emit)
        card.row_selected.connect(self.row_selected.emit)
        card.add_watchlist_requested.connect(self.add_watchlist_requested.emit)
        card.batch_add_watchlist_requested.connect(self.batch_add_watchlist_requested.emit)
        card.stock_analysis_requested.connect(self.stock_analysis_requested.emit)
        card.view_run_requested.connect(self.view_run_requested.emit)
        card.sector_flow_requested.connect(self.sector_flow_requested.emit)
        card.sector_rotation_requested.connect(self.sector_rotation_requested.emit)
        card.refresh_requested.connect(self.refresh_requested.emit)
        card.quote_refresh_requested.connect(self.quote_refresh_requested.emit)
        card.ai_requested.connect(self.ai_requested.emit)
        card.auto_refresh_changed.connect(self.auto_refresh_changed.emit)
        card.full_refresh_interval_changed.connect(self.full_refresh_interval_changed.emit)
        self._cards[spec.id] = card
        return card

    def card(self, card_id: str) -> RadarCardWidget | None:
        return self._cards.get(card_id)

    def visible_card_ids_for_current_group(self) -> list[str]:
        mode = self.current_mode()
        return self.visible_card_ids_in_group(mode, self.current_group(mode))

    def visible_card_ids_in_group(self, mode: RadarCardMode, group_key: RadarGroupKey) -> list[str]:
        """返回分组内当前视口可见的卡片 id（按网格顺序）；不可见时回退首行。"""
        specs = list_radar_cards_for_group(mode, group_key)
        if not specs:
            return []
        scroll = self._group_scrolls.get((mode, group_key))
        if scroll is None:
            return [spec.id for spec in specs[:RADAR_GRID_COLUMNS]]
        viewport = scroll.viewport()
        if viewport is None:
            return [spec.id for spec in specs[:RADAR_GRID_COLUMNS]]
        viewport_rect = viewport.rect()
        visible: list[str] = []
        for spec in specs:
            card = self._cards.get(spec.id)
            if card is None or not card.isVisible():
                continue
            top_left = card.mapTo(viewport, QtCore.QPoint(0, 0))
            card_rect = QtCore.QRect(top_left, card.size())
            if viewport_rect.intersects(card_rect):
                visible.append(spec.id)
        if visible:
            return visible
        return [spec.id for spec in specs[:RADAR_GRID_COLUMNS]]

    def focus_card(self, card_id: str) -> bool:
        """切换分区并滚动到指定卡片。"""
        widget = self._cards.get(card_id)
        if widget is None:
            return False
        mode = widget._spec.mode
        group_key = radar_card_group(card_id)
        self.set_mode(mode, persist=False)
        if group_key is not None:
            self.set_group(mode, group_key, persist=False)

        def _scroll() -> None:
            parent = widget.parentWidget()
            while parent is not None and not isinstance(parent, QtWidgets.QScrollArea):
                parent = parent.parentWidget()
            if parent is not None:
                parent.ensureWidgetVisible(widget, 0, 64)

        QtCore.QTimer.singleShot(0, _scroll)
        return True

    def sync_mode_badges(self) -> None:
        for widget in self._cards.values():
            widget.update_mode_badge()

    def apply_board(self, payload: dict[str, RadarCardData]) -> None:
        resonance = compute_radar_resonance(payload)
        for card_id, data in payload.items():
            self.apply_card(card_id, data, resonance_counts=resonance)

    def apply_card(
        self,
        card_id: str,
        data: RadarCardData,
        *,
        resonance_counts: dict[str, int] | None = None,
    ) -> None:
        widget = self._cards.get(card_id)
        if widget is not None:
            widget.apply_data(data, resonance_counts=resonance_counts)

    def sync_resonance(self, resonance_counts: dict[str, int]) -> None:
        for widget in self._cards.values():
            widget.update_resonance(resonance_counts)

    def apply_quote_update(self, card_id: str, rows: tuple) -> None:
        widget = self._cards.get(card_id)
        if widget is not None:
            widget.apply_quote_update(rows)
