"""雷达看板：分区 Tab + 分组网格。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.quotes.radar.loaders import RadarCardData, compute_radar_resonance
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
    list_radar_cards_for_group,
    list_radar_groups_for_mode,
    radar_card_group,
)
from vnpy_ashare.ui.quotes.radar.card import RadarCardWidget
from vnpy_ashare.ui.quotes.radar.card_layout import estimate_card_min_height, fallback_visible_card_ids
from vnpy_ashare.ui.quotes.radar.section_prefs import (
    load_radar_board_group,
    load_radar_board_mode,
    save_radar_board_group,
    save_radar_board_mode,
)
from vnpy_common.ui.panel_widgets import configure_document_tab_widget


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
        card.setMinimumHeight(estimate_card_min_height(spec.top_n))
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
        all_ids = [spec.id for spec in specs]
        scroll = self._group_scrolls.get((mode, group_key))
        if scroll is None:
            return fallback_visible_card_ids(all_ids, RADAR_GRID_COLUMNS)
        viewport = scroll.viewport()
        if viewport is None:
            return fallback_visible_card_ids(all_ids, RADAR_GRID_COLUMNS)
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
        return fallback_visible_card_ids(all_ids, RADAR_GRID_COLUMNS)

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
