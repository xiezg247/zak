"""雷达页单卡 UI。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.time.market_hours import ashare_market_phase, ashare_market_phase_label
from vnpy_ashare.quotes.radar.loaders import RadarCardData, RadarRow
from vnpy_ashare.quotes.radar.radar_catalog import (
    RadarCardSpec,
    default_refresh_ms_for_card,
    default_variant_for_card,
    full_refresh_options_for_card,
    refresh_options_for_card,
    supports_auto_refresh,
    variants_for_card,
)
from vnpy_ashare.quotes.radar.radar_full_refresh_prefs import load_radar_full_refresh_every
from vnpy_ashare.ui.quotes.page.config import load_radar_card_refresh_ms
from vnpy_ashare.ui.quotes.radar.card_layout import (
    BODY_PAGE_EMPTY,
    BODY_PAGE_ROWS,
    RADAR_ROW_SPACING,
    card_frame_object_name,
    count_resonance_hits,
    estimate_card_min_height,
    format_card_meta,
    kind_badge_presentation,
    mode_badge_presentation,
)
from vnpy_ashare.ui.quotes.radar.row_widget import RadarStockRowWidget
from vnpy_common.ui.theme.manager import theme_manager


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
        self.setObjectName(
            card_frame_object_name(
                mode=spec.mode,
                supports_auto_refresh=self._supports_auto_refresh,
            )
        )
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        self.setMinimumHeight(estimate_card_min_height(spec.top_n))

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

        kind_text, kind_object = kind_badge_presentation(spec.mode)
        self._kind_badge = QtWidgets.QLabel(kind_text)
        self._kind_badge.setObjectName(kind_object)
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
        self._rows_layout.setSpacing(RADAR_ROW_SPACING)

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
        self._body_stack.setCurrentIndex(BODY_PAGE_ROWS)
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
        text, object_name = mode_badge_presentation(
            supports_auto_refresh=self._supports_auto_refresh,
            phase=ashare_market_phase(),
            phase_label=ashare_market_phase_label(),
        )
        self._mode_badge.setText(text)
        self._mode_badge.setObjectName(object_name)
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
            card_resonance = count_resonance_hits(
                [w.vt_symbol() for w in self._row_widgets],
                self._resonance_counts,
            )
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
            data.subtitle,
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
            self._body_stack.setCurrentIndex(BODY_PAGE_ROWS)
            quote_by_vt = {row.vt_symbol: row for row in data.rows}
            for widget in self._row_widgets:
                row = quote_by_vt.get(widget.vt_symbol())
                if row is not None:
                    widget.refresh_row(row)
                    widget.update_resonance(self._resonance_counts.get(row.vt_symbol, 0))
            return
        self._clear_row_widgets()
        if data.rows:
            self._body_stack.setCurrentIndex(BODY_PAGE_ROWS)
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
        self._body_stack.setCurrentIndex(BODY_PAGE_EMPTY)

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
        card_resonance = count_resonance_hits(
            [row.vt_symbol for row in data.rows],
            self._resonance_counts,
        )
        self._apply_meta_label_from_resonance(card_resonance)

    def _apply_meta_label_from_resonance(self, card_resonance: int) -> None:
        self._meta_label.setText(
            format_card_meta(
                updated_at_text=self._updated_at_text,
                card_resonance=card_resonance,
            )
        )

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
