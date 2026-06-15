"""雷达页共振列表侧栏。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.quotes.radar.radar_loaders import RadarResonanceEntry
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color


class RadarResonancePanel(QtWidgets.QFrame):
    """全局共振标的汇总侧栏。"""

    row_activated = QtCore.Signal(str)
    row_selected = QtCore.Signal(str)
    add_watchlist_requested = QtCore.Signal(str)
    batch_add_watchlist_requested = QtCore.Signal()
    stock_analysis_requested = QtCore.Signal(str)
    ai_resonance_requested = QtCore.Signal()
    open_screener_requested = QtCore.Signal()
    resonance_weights_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RadarResonancePanel")
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setMinimumWidth(200)
        self.setMaximumWidth(360)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("共振列表")
        title.setObjectName("RadarResonanceTitle")
        header.addWidget(title, stretch=1)
        self._count_label = QtWidgets.QLabel("0")
        self._count_label.setObjectName("RadarResonanceCount")
        header.addWidget(self._count_label)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(6)
        self._add_all_button = QtWidgets.QPushButton("全部加自选")
        self._add_all_button.setObjectName("RadarResonanceAddAll")
        self._add_all_button.clicked.connect(self.batch_add_watchlist_requested.emit)
        self._ai_button = QtWidgets.QPushButton("AI 解读")
        self._ai_button.setObjectName("RadarResonanceAi")
        self._ai_button.clicked.connect(self.ai_resonance_requested.emit)
        self._screener_button = QtWidgets.QPushButton("条件选股")
        self._screener_button.setObjectName("RadarResonanceScreener")
        self._screener_button.clicked.connect(self.open_screener_requested.emit)
        self._weights_button = QtWidgets.QPushButton("权重")
        self._weights_button.setObjectName("RadarResonanceWeights")
        self._weights_button.setToolTip("配置各卡片共振加权分")
        self._weights_button.clicked.connect(self.resonance_weights_requested.emit)
        toolbar.addWidget(self._add_all_button)
        toolbar.addWidget(self._ai_button)
        toolbar.addWidget(self._screener_button)
        toolbar.addWidget(self._weights_button)

        self._list = QtWidgets.QListWidget()
        self._list.setObjectName("RadarResonanceList")
        self._list.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)

        self._empty_label = QtWidgets.QLabel("暂无共振标的\n（需同时出现在 2 张及以上卡片）")
        self._empty_label.setObjectName("RadarResonanceEmpty")
        self._empty_label.setWordWrap(True)
        self._empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addLayout(toolbar)
        layout.addWidget(self._list, stretch=1)
        layout.addWidget(self._empty_label)

        self._entries: tuple[RadarResonanceEntry, ...] = ()
        self._set_actions_enabled(False)
        theme_manager().register_callback(lambda _tokens: self._refresh_list_colors())

    def apply_entries(self, entries: tuple[RadarResonanceEntry, ...]) -> None:
        self._entries = entries
        self._count_label.setText(str(len(entries)))
        self._list.clear()
        has_entries = bool(entries)
        self._set_actions_enabled(has_entries)
        if not has_entries:
            self._list.hide()
            self._empty_label.show()
            return
        self._empty_label.hide()
        self._list.show()
        tokens = theme_manager().tokens()
        for entry in entries:
            item = QtWidgets.QListWidgetItem(self._format_entry_text(entry))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, entry.vt_symbol)
            item.setData(QtCore.Qt.ItemDataRole.UserRole + 1, entry.change_pct)
            item.setForeground(QtGui.QColor(pct_change_color(entry.change_pct, tokens)))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self._list.addItem(item)

    def entries(self) -> tuple[RadarResonanceEntry, ...]:
        return self._entries

    def _set_actions_enabled(self, enabled: bool) -> None:
        self._add_all_button.setEnabled(enabled)
        self._ai_button.setEnabled(enabled)
        self._screener_button.setEnabled(enabled)

    def _format_entry_text(self, entry: RadarResonanceEntry) -> str:
        price = f"{entry.price:.2f}" if entry.price is not None else "—"
        change = f"{entry.change_pct:+.2f}%" if entry.change_pct is not None else "—"
        cards = " · ".join(entry.card_titles)
        score_note = f"  加权{entry.resonance_score:.1f}" if entry.resonance_score > 0 else ""
        return f"{entry.name}  {entry.symbol}\n{entry.card_count}卡{score_note}  {price}  {change}\n{cards}"

    def _refresh_list_colors(self) -> None:
        tokens = theme_manager().tokens()
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item is None:
                continue
            change_pct = item.data(QtCore.Qt.ItemDataRole.UserRole + 1)
            value = float(change_pct) if isinstance(change_pct, (int, float)) else None
            item.setForeground(QtGui.QColor(pct_change_color(value, tokens)))

    def _on_item_double_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        vt_symbol = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if vt_symbol:
            self.row_activated.emit(str(vt_symbol))

    def _on_item_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        vt_symbol = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if vt_symbol:
            self.row_selected.emit(str(vt_symbol))

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
