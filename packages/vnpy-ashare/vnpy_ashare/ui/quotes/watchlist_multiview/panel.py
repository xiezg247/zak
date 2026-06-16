"""自选多维看盘网格面板。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.quotes.watchlist_multiview.models import WatchlistMultiBoardData, WatchlistMultiRow
from vnpy_ashare.ui.quotes.watchlist_multiview.card import WatchlistMultiCard
from vnpy_ashare.ui.quotes.watchlist_multiview.settings import load_grid_columns
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.build_extra import build_watchlist_multiview_stylesheet


class WatchlistMultiViewBoard(QtWidgets.QWidget):
    """自选池多维卡片网格。"""

    row_clicked = QtCore.Signal(str)
    row_double_clicked = QtCore.Signal(str)
    row_context_menu_requested = QtCore.Signal(str, object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("WatchlistMultiViewBoard")

        self._summary = QtWidgets.QLabel("")
        self._summary.setObjectName("WatchlistMultiSummary")
        self._empty_label = QtWidgets.QLabel("")
        self._empty_label.setObjectName("WatchlistMultiEmpty")
        self._empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._empty_label.hide()

        self._grid_host = QtWidgets.QWidget()
        self._grid_host.setObjectName("WatchlistMultiGridHost")
        self._grid = QtWidgets.QGridLayout(self._grid_host)
        self._grid.setContentsMargins(8, 4, 8, 8)
        self._grid.setSpacing(8)

        scroll = QtWidgets.QScrollArea()
        scroll.setObjectName("WatchlistMultiScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(self._grid_host)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._summary)
        layout.addWidget(scroll, stretch=1)
        layout.addWidget(self._empty_label)

        theme_manager().bind_stylesheet(self, extra=build_watchlist_multiview_stylesheet)

        self._cards: list[WatchlistMultiCard] = []
        self._rows: tuple[WatchlistMultiRow, ...] = ()
        self._selected_vt_symbol = ""
        self._grid_columns = load_grid_columns()

    def set_grid_columns(self, columns: int) -> None:
        self._grid_columns = max(2, min(4, int(columns)))
        self._rebuild_grid()

    def apply_board(self, data: WatchlistMultiBoardData) -> None:
        new_keys = [row.vt_symbol for row in data.rows]
        old_keys = [row.vt_symbol for row in self._rows]
        if new_keys == old_keys and len(self._cards) == len(data.rows) and data.rows:
            self._rows = data.rows
            self._update_summary(data.rows)
            for card, row in zip(self._cards, data.rows, strict=True):
                card.apply_row(row, selected=row.vt_symbol == self._selected_vt_symbol)
            return

        self._rows = data.rows
        if not data.rows:
            self._summary.setText("")
            self._empty_label.setText(data.empty_message or "暂无数据")
            self._empty_label.show()
            self._clear_cards()
            return
        self._empty_label.hide()
        self._update_summary(data.rows)
        self._rebuild_grid()

    def _update_summary(self, rows: tuple[WatchlistMultiRow, ...]) -> None:
        rise = sum(1 for row in rows if (row.change_pct or 0) > 0)
        fall = sum(1 for row in rows if (row.change_pct or 0) < 0)
        flat = len(rows) - rise - fall
        self._summary.setText(f"共 {len(rows)} 只 · 涨 {rise} / 跌 {fall} / 平 {flat}")

    def highlight_symbol(self, vt_symbol: str | None) -> None:
        target = (vt_symbol or "").strip()
        self._selected_vt_symbol = target
        for card in self._cards:
            card.set_selected(bool(target) and card.vt_symbol() == target)

    def _clear_cards(self) -> None:
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards = []
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def _rebuild_grid(self) -> None:
        self._clear_cards()
        columns = self._grid_columns
        for index, row in enumerate(self._rows):
            card = WatchlistMultiCard(self._grid_host)
            card.apply_row(row, selected=row.vt_symbol == self._selected_vt_symbol)
            card.clicked.connect(self.row_clicked.emit)
            card.double_clicked.connect(self.row_double_clicked.emit)
            card.context_menu_requested.connect(self._on_card_context_menu)
            self._cards.append(card)
            self._grid.addWidget(card, index // columns, index % columns)
        row_count = max(1, (len(self._rows) + columns - 1) // columns)
        for col in range(columns):
            self._grid.setColumnStretch(col, 1)
        for grid_row in range(row_count):
            self._grid.setRowStretch(grid_row, 0)

    def _on_card_context_menu(self, vt_symbol: str, global_pos: object) -> None:
        self.row_context_menu_requested.emit(vt_symbol, global_pos)
