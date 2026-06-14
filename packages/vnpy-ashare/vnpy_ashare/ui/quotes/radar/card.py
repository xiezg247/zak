"""雷达页卡片 UI。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.market_hours import ashare_market_phase, ashare_market_phase_label
from vnpy_ashare.quotes.radar_catalog import (
    RadarCardSpec,
    default_refresh_ms_for_card,
    default_variant_for_card,
    refresh_options_for_card,
    supports_auto_refresh,
    variants_for_card,
)
from vnpy_ashare.quotes.radar_loaders import RadarCardData
from vnpy_ashare.ui.quotes.page.config import load_radar_card_refresh_ms
from vnpy_ashare.ui.quotes.radar.row_widget import RadarStockRowWidget
from vnpy_common.ui.theme import theme_manager


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
    refresh_requested = QtCore.Signal(str)
    ai_requested = QtCore.Signal(str)
    auto_refresh_changed = QtCore.Signal(str, int)

    def __init__(self, spec: RadarCardSpec, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._spec = spec
        self._supports_auto_refresh = supports_auto_refresh(spec.id)
        object_name = "RadarCardLive" if self._supports_auto_refresh else "RadarCardManual"
        self.setObjectName(object_name)
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)

        header = QtWidgets.QHBoxLayout()
        self._title = QtWidgets.QLabel(spec.title)
        self._title.setObjectName("RadarCardTitle")
        header.addWidget(self._title, stretch=1)

        self._mode_badge = QtWidgets.QLabel("")
        self._mode_badge.setObjectName("RadarCardModeBadge")
        self._update_mode_badge()
        header.addWidget(self._mode_badge)

        self._variant_combo = QtWidgets.QComboBox()
        self._variant_combo.setObjectName("RadarCardVariant")
        if spec.has_task_variants:
            for variant in variants_for_card(spec.id):
                self._variant_combo.addItem(variant.label, variant.key)
            default_key = default_variant_for_card(spec.id)
            if default_key:
                self.set_variant_key(default_key)
            self._variant_combo.currentIndexChanged.connect(self._emit_variant_changed)
            header.addWidget(self._variant_combo)
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
            header.addWidget(self._refresh_interval_combo)
        else:
            self._refresh_interval_combo.hide()

        self._refresh_button = QtWidgets.QToolButton()
        self._refresh_button.setObjectName("RadarCardRefresh")
        self._refresh_button.setText("↻")
        self._refresh_button.setToolTip("刷新此卡片")
        self._refresh_button.clicked.connect(lambda: self.refresh_requested.emit(self.card_id))
        header.addWidget(self._refresh_button)

        self._subtitle = QtWidgets.QLabel("")
        self._subtitle.setObjectName("RadarCardSubtitle")
        self._subtitle.setWordWrap(True)

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
        if spec.id == "sector_theme":
            self._sector_flow_button = QtWidgets.QPushButton("板块资金")
            self._sector_flow_button.setObjectName("RadarCardSectorFlow")
            self._sector_flow_button.setFlat(True)
            self._sector_flow_button.setToolTip("打开板块资金监控页并预选主线行业")
            self._sector_flow_button.clicked.connect(lambda: self.sector_flow_requested.emit(self.card_id))
            footer.addWidget(self._sector_flow_button)
        else:
            self._sector_flow_button = None
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
        self._subtitle.setText(data.subtitle)
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

    def _on_view_run_clicked(self) -> None:
        if self._run_id and self._detail_page_key:
            self.view_run_requested.emit(self._run_id, self._detail_page_key)


class RadarBoard(QtWidgets.QWidget):
    """雷达卡片网格（默认 3 列）。"""

    variant_changed = QtCore.Signal(str, str)
    row_activated = QtCore.Signal(str)
    row_selected = QtCore.Signal(str)
    add_watchlist_requested = QtCore.Signal(str)
    batch_add_watchlist_requested = QtCore.Signal(str)
    stock_analysis_requested = QtCore.Signal(str)
    view_run_requested = QtCore.Signal(str, str)
    sector_flow_requested = QtCore.Signal(str)
    refresh_requested = QtCore.Signal(str)
    ai_requested = QtCore.Signal(str)
    auto_refresh_changed = QtCore.Signal(str, int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RadarBoard")
        from vnpy_ashare.quotes.radar_catalog import RADAR_GRID_COLUMNS, list_radar_cards

        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(10)
        self._cards: dict[str, RadarCardWidget] = {}
        specs = list_radar_cards()
        columns = RADAR_GRID_COLUMNS
        for index, spec in enumerate(specs):
            card = RadarCardWidget(spec, self)
            card.variant_changed.connect(lambda key, card_id=spec.id: self.variant_changed.emit(card_id, key))
            card.row_activated.connect(self.row_activated.emit)
            card.row_selected.connect(self.row_selected.emit)
            card.add_watchlist_requested.connect(self.add_watchlist_requested.emit)
            card.batch_add_watchlist_requested.connect(self.batch_add_watchlist_requested.emit)
            card.stock_analysis_requested.connect(self.stock_analysis_requested.emit)
            card.view_run_requested.connect(self.view_run_requested.emit)
            card.sector_flow_requested.connect(self.sector_flow_requested.emit)
            card.refresh_requested.connect(self.refresh_requested.emit)
            card.ai_requested.connect(self.ai_requested.emit)
            card.auto_refresh_changed.connect(self.auto_refresh_changed.emit)
            self._cards[spec.id] = card
            grid.addWidget(card, index // columns, index % columns)
        row_count = max(1, (len(specs) + columns - 1) // columns)
        for col in range(columns):
            grid.setColumnStretch(col, 1)
        for row in range(row_count):
            grid.setRowStretch(row, 1)

    def card(self, card_id: str) -> RadarCardWidget | None:
        return self._cards.get(card_id)

    def sync_mode_badges(self) -> None:
        for widget in self._cards.values():
            widget.update_mode_badge()

    def apply_board(self, payload: dict[str, RadarCardData]) -> None:
        from vnpy_ashare.quotes.radar_loaders import compute_radar_resonance

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
