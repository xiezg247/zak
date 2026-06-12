"""雷达页卡片 UI。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.quotes.radar_catalog import SCREEN_TASK_VARIANTS, RadarCardSpec
from vnpy_ashare.quotes.radar_loaders import RadarCardData, RadarRow
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color


class RadarCardWidget(QtWidgets.QFrame):
    """单张雷达卡片。"""

    variant_changed = QtCore.Signal(str)
    row_activated = QtCore.Signal(str)
    add_watchlist_requested = QtCore.Signal(str)
    stock_analysis_requested = QtCore.Signal(str)

    def __init__(self, spec: RadarCardSpec, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._spec = spec
        self.setObjectName("RadarCard")
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)

        header = QtWidgets.QHBoxLayout()
        self._title = QtWidgets.QLabel(spec.title)
        self._title.setObjectName("RadarCardTitle")
        header.addWidget(self._title, stretch=1)

        self._variant_combo = QtWidgets.QComboBox()
        self._variant_combo.setObjectName("RadarCardVariant")
        if spec.has_task_variants:
            for variant in SCREEN_TASK_VARIANTS:
                self._variant_combo.addItem(variant.label, variant.key)
            self._variant_combo.currentIndexChanged.connect(self._emit_variant_changed)
            header.addWidget(self._variant_combo)
        else:
            self._variant_combo.hide()

        self._subtitle = QtWidgets.QLabel("")
        self._subtitle.setObjectName("RadarCardSubtitle")
        self._subtitle.setWordWrap(True)

        self._list = QtWidgets.QListWidget()
        self._list.setObjectName("RadarCardList")
        self._list.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._list.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)

        self._empty_label = QtWidgets.QLabel("")
        self._empty_label.setObjectName("RadarCardEmpty")
        self._empty_label.setWordWrap(True)
        self._empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addWidget(self._subtitle)
        layout.addWidget(self._list, stretch=1)
        layout.addWidget(self._empty_label)

        theme_manager().register_callback(lambda _tokens: self._refresh_list_colors())

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

    def apply_data(self, data: RadarCardData) -> None:
        self._subtitle.setText(data.subtitle)
        self._list.clear()
        if data.rows:
            self._list.show()
            self._empty_label.hide()
            tokens = theme_manager().tokens()
            for row in data.rows:
                item = QtWidgets.QListWidgetItem(self._format_row_text(row))
                item.setData(QtCore.Qt.ItemDataRole.UserRole, row.vt_symbol)
                item.setData(QtCore.Qt.ItemDataRole.UserRole + 1, row.change_pct)
                color = pct_change_color(row.change_pct, tokens)
                item.setForeground(QtGui.QColor(color))
                self._list.addItem(item)
            return
        self._list.hide()
        self._empty_label.show()
        self._empty_label.setText(data.empty_message or "暂无数据")

    def _format_row_text(self, row: RadarRow) -> str:
        price = f"{row.price:.2f}" if row.price is not None else "—"
        change = f"{row.change_pct:+.2f}%" if row.change_pct is not None else "—"
        return f"{row.name:<6} {row.symbol}\n{price:>8}  {row.metric_label} {row.metric_value}  {change}"

    def _refresh_list_colors(self) -> None:
        tokens = theme_manager().tokens()
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item is None:
                continue
            change_pct = item.data(QtCore.Qt.ItemDataRole.UserRole + 1)
            value = float(change_pct) if isinstance(change_pct, (int, float)) else None
            item.setForeground(QtGui.QColor(pct_change_color(value, tokens)))

    def _emit_variant_changed(self, _index: int) -> None:
        key = self.variant_key()
        if key:
            self.variant_changed.emit(key)

    def _on_item_double_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        vt_symbol = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if vt_symbol:
            self.row_activated.emit(str(vt_symbol))

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self._list.itemAt(pos)
        if item is None:
            return
        vt_symbol = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not vt_symbol:
            return
        menu = QtWidgets.QMenu(self)
        analysis_action = menu.addAction("个股分析")
        action = menu.addAction("加入自选")
        chosen = menu.exec(self._list.mapToGlobal(pos))
        if chosen is analysis_action:
            self.stock_analysis_requested.emit(str(vt_symbol))
        elif chosen is action:
            self.add_watchlist_requested.emit(str(vt_symbol))


class RadarBoard(QtWidgets.QWidget):
    """2×2 雷达卡片网格。"""

    variant_changed = QtCore.Signal(str, str)
    row_activated = QtCore.Signal(str)
    add_watchlist_requested = QtCore.Signal(str)
    stock_analysis_requested = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RadarBoard")
        from vnpy_ashare.quotes.radar_catalog import list_radar_cards

        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(10)
        self._cards: dict[str, RadarCardWidget] = {}
        specs = list_radar_cards()
        for index, spec in enumerate(specs):
            card = RadarCardWidget(spec, self)
            card.variant_changed.connect(lambda key, card_id=spec.id: self.variant_changed.emit(card_id, key))
            card.row_activated.connect(self.row_activated.emit)
            card.add_watchlist_requested.connect(self.add_watchlist_requested.emit)
            card.stock_analysis_requested.connect(self.stock_analysis_requested.emit)
            self._cards[spec.id] = card
            grid.addWidget(card, index // 2, index % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

    def card(self, card_id: str) -> RadarCardWidget | None:
        return self._cards.get(card_id)

    def apply_board(self, payload: dict[str, RadarCardData]) -> None:
        for card_id, data in payload.items():
            widget = self._cards.get(card_id)
            if widget is not None:
                widget.apply_data(data)
