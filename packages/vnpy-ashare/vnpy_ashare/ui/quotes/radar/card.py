"""雷达页卡片 UI。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.market_hours import ashare_market_phase, ashare_market_phase_label
from vnpy_ashare.quotes.market.emotion_cycle_subtitle import append_emotion_cycle_to_subtitle
from vnpy_ashare.quotes.radar.radar_catalog import (
    RADAR_GRID_COLUMNS,
    RADAR_LAYOUT_SECTIONS,
    RadarCardMode,
    RadarCardSpec,
    default_refresh_ms_for_card,
    default_variant_for_card,
    full_refresh_options_for_card,
    list_radar_cards_for_mode,
    refresh_options_for_card,
    supports_auto_refresh,
    variants_for_card,
)
from vnpy_ashare.quotes.radar.radar_full_refresh_prefs import load_radar_full_refresh_every
from vnpy_ashare.quotes.radar.radar_loaders import RadarCardData, RadarRow
from vnpy_ashare.ui.quotes.page.config import load_radar_card_refresh_ms
from vnpy_ashare.ui.quotes.radar.row_widget import RadarStockRowWidget
from vnpy_ashare.ui.quotes.radar.section_prefs import load_radar_board_mode, save_radar_board_mode
from vnpy_common.ui.panel_widgets import configure_document_tab_widget
from vnpy_common.ui.theme import theme_manager

_OBSERVATION_GROUP_CARD_IDS = frozenset(
    {
        "leader_pick",
        "discovery_first_board",
        "discovery_limit_ladder",
    }
)


class RadarCardWidget(QtWidgets.QFrame):
    """单张雷达卡片。"""

    variant_changed = QtCore.Signal(str)
    row_activated = QtCore.Signal(str)
    row_selected = QtCore.Signal(str)
    add_watchlist_requested = QtCore.Signal(str)
    batch_add_watchlist_requested = QtCore.Signal(str)
    add_observation_group_requested = QtCore.Signal(str)
    stock_analysis_requested = QtCore.Signal(str)
    view_run_requested = QtCore.Signal(str, str)
    sector_flow_requested = QtCore.Signal(str)
    refresh_requested = QtCore.Signal(str)
    quote_refresh_requested = QtCore.Signal(str)
    ai_requested = QtCore.Signal(str)
    train_model_requested = QtCore.Signal(str)
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
        self._subtitle.setMinimumHeight(15)

        self._ai_hint = QtWidgets.QLabel("")
        self._ai_hint.setObjectName("RadarCardAiHint")
        self._ai_hint.setWordWrap(True)
        self._ai_hint.hide()

        self._rows_host = QtWidgets.QWidget()
        self._rows_host.setObjectName("RadarCardRowsHost")
        self._rows_layout = QtWidgets.QVBoxLayout(self._rows_host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(4)
        self._rows_layout.addStretch(1)

        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setObjectName("RadarCardScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidget(self._rows_host)

        self._empty_label = QtWidgets.QLabel("")
        self._empty_label.setObjectName("RadarCardEmpty")
        self._empty_label.setWordWrap(True)
        self._empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

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
        if spec.id == "sector_theme":
            self._sector_flow_button = QtWidgets.QPushButton("板块资金")
            self._sector_flow_button.setObjectName("RadarCardSectorFlow")
            self._sector_flow_button.setFlat(True)
            self._sector_flow_button.setToolTip("打开板块资金监控页并预选主线行业")
            self._sector_flow_button.clicked.connect(lambda: self.sector_flow_requested.emit(self.card_id))
            footer.addWidget(self._sector_flow_button)
        else:
            self._sector_flow_button = None
        self._train_model_button: QtWidgets.QPushButton | None = None
        if spec.id == "outlook_predict":
            self._train_model_button = QtWidgets.QPushButton("训练模型…")
            self._train_model_button.setObjectName("RadarCardTrainModel")
            self._train_model_button.setFlat(True)
            self._train_model_button.setToolTip("训练或更新 LightGBM 预测模型")
            self._train_model_button.clicked.connect(lambda: self.train_model_requested.emit(self.card_id))
            footer.addWidget(self._train_model_button)
        else:
            self._train_model_button = None
        self._observation_group_button: QtWidgets.QPushButton | None = None
        if spec.id in _OBSERVATION_GROUP_CARD_IDS:
            self._observation_group_button = QtWidgets.QPushButton("加观察组")
            self._observation_group_button.setObjectName("RadarCardObservationGroup")
            self._observation_group_button.setFlat(True)
            self._observation_group_button.setToolTip("加入自选并写入「短线观察」分组")
            self._observation_group_button.clicked.connect(
                lambda: self.add_observation_group_requested.emit(self.card_id),
            )
            footer.addWidget(self._observation_group_button)
        self._add_all_button = QtWidgets.QPushButton("全部加自选")
        self._add_all_button.setObjectName("RadarCardAddAll")
        self._add_all_button.setFlat(True)
        self._add_all_button.hide()
        self._add_all_button.clicked.connect(self._on_add_all_clicked)
        footer.addWidget(self._add_all_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addWidget(self._subtitle)
        layout.addWidget(self._ai_hint)
        layout.addWidget(self._scroll, stretch=1)
        layout.addWidget(self._empty_label)
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
        while self._rows_layout.count() > 1:
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
            if self._observation_group_button is not None:
                self._observation_group_button.show()
        else:
            self._add_all_button.hide()
            if self._observation_group_button is not None:
                self._observation_group_button.hide()
        self._apply_meta_label(data)
        self._clear_row_widgets()
        if data.rows:
            self._scroll.show()
            self._empty_label.hide()
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
                self._rows_layout.insertWidget(self._rows_layout.count() - 1, widget)
                self._row_widgets.append(widget)
            return
        self._scroll.hide()
        self._empty_label.show()
        self._empty_label.setText(data.empty_message or "暂无数据")

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
    add_observation_group_requested = QtCore.Signal(str)
    stock_analysis_requested = QtCore.Signal(str)
    view_run_requested = QtCore.Signal(str, str)
    sector_flow_requested = QtCore.Signal(str)
    refresh_requested = QtCore.Signal(str)
    quote_refresh_requested = QtCore.Signal(str)
    ai_requested = QtCore.Signal(str)
    train_model_requested = QtCore.Signal(str)
    auto_refresh_changed = QtCore.Signal(str, int)
    full_refresh_interval_changed = QtCore.Signal(str, int)
    mode_changed = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RadarBoard")

        self._cards: dict[str, RadarCardWidget] = {}
        self._mode_tab_index: dict[RadarCardMode, int] = {}

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
            page_layout.setSpacing(0)

            scroll = QtWidgets.QScrollArea()
            scroll.setObjectName("RadarBoardScroll")
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

            section_host = QtWidgets.QWidget()
            section_host.setObjectName(f"RadarSectionGrid{section.mode.title()}")
            grid = QtWidgets.QGridLayout(section_host)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(10)

            specs = list_radar_cards_for_mode(section.mode)
            for index, spec in enumerate(specs):
                card = self._wire_card(spec)
                grid.addWidget(card, index // columns, index % columns)

            row_count = max(1, (len(specs) + columns - 1) // columns)
            for col in range(columns):
                grid.setColumnStretch(col, 1)
            for row in range(row_count):
                grid.setRowStretch(row, 1)

            scroll.setWidget(section_host)
            page_layout.addWidget(scroll, stretch=1)

            self._tabs.addTab(page, section.title)
            self._tabs.setTabToolTip(section_index, section.hint)
            self._mode_tab_index[section.mode] = section_index

        self._tabs.currentChanged.connect(self._on_tab_changed)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._tabs)

        self.set_mode(load_radar_board_mode(), persist=False)
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

    def update_tab_badges(self) -> None:
        from vnpy_ashare.quotes.radar.predict.model_paths import (
            lightgbm_unavailable_hint,
            lightgbm_unavailable_reason,
            should_retrain_predict_model,
        )

        for section_index, section in enumerate(RADAR_LAYOUT_SECTIONS):
            title = section.title
            tooltip = section.hint
            if section.mode == "predictive":
                if lightgbm_unavailable_reason() is not None:
                    title = f"{title} ·"
                    tooltip = f"{section.hint}\n{lightgbm_unavailable_hint()}"
                elif should_retrain_predict_model():
                    title = f"{title} ·"
                    tooltip = f"{section.hint}\n建议重训预测模型"
            self._tabs.setTabText(section_index, title)
            self._tabs.setTabToolTip(section_index, tooltip)

    def _on_tab_changed(self, index: int) -> None:
        if index < 0 or index >= len(RADAR_LAYOUT_SECTIONS):
            return
        mode = RADAR_LAYOUT_SECTIONS[index].mode
        save_radar_board_mode(mode)
        self.mode_changed.emit(mode)

    def _wire_card(self, spec: RadarCardSpec) -> RadarCardWidget:
        card = RadarCardWidget(spec, self)
        card.variant_changed.connect(lambda key, card_id=spec.id: self.variant_changed.emit(card_id, key))
        card.row_activated.connect(self.row_activated.emit)
        card.row_selected.connect(self.row_selected.emit)
        card.add_watchlist_requested.connect(self.add_watchlist_requested.emit)
        card.batch_add_watchlist_requested.connect(self.batch_add_watchlist_requested.emit)
        card.add_observation_group_requested.connect(self.add_observation_group_requested.emit)
        card.stock_analysis_requested.connect(self.stock_analysis_requested.emit)
        card.view_run_requested.connect(self.view_run_requested.emit)
        card.sector_flow_requested.connect(self.sector_flow_requested.emit)
        card.refresh_requested.connect(self.refresh_requested.emit)
        card.quote_refresh_requested.connect(self.quote_refresh_requested.emit)
        card.ai_requested.connect(self.ai_requested.emit)
        card.train_model_requested.connect(self.train_model_requested.emit)
        card.auto_refresh_changed.connect(self.auto_refresh_changed.emit)
        card.full_refresh_interval_changed.connect(self.full_refresh_interval_changed.emit)
        self._cards[spec.id] = card
        return card

    def card(self, card_id: str) -> RadarCardWidget | None:
        return self._cards.get(card_id)

    def sync_mode_badges(self) -> None:
        for widget in self._cards.values():
            widget.update_mode_badge()

    def apply_board(self, payload: dict[str, RadarCardData]) -> None:
        from vnpy_ashare.quotes.radar.radar_loaders import compute_radar_resonance

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
