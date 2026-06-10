"""市场页表格加载遮罩。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

_HIDE_TABLE_SCROLLBAR_QSS = """
QTableView#MarketTable QScrollBar:vertical {
    width: 0px;
    max-width: 0px;
    min-width: 0px;
    margin: 0;
    background: transparent;
}
QTableView#MarketTable QScrollBar:vertical::handle,
QTableView#MarketTable QScrollBar:vertical::add-page,
QTableView#MarketTable QScrollBar:vertical::sub-page,
QTableView#MarketTable QScrollBar:vertical::add-line,
QTableView#MarketTable QScrollBar:vertical::sub-line {
    width: 0px;
    height: 0px;
    background: transparent;
    border: none;
}
"""

_MARKET_SCROLL_RAIL_QSS = """
QScrollBar#MarketTableScroll:vertical {
    background-color: #3a3a48;
    width: 18px;
    margin: 0;
    border: none;
    border-left: 1px solid #5a8fd8;
}
QScrollBar#MarketTableScroll::handle:vertical {
    background-color: #8a96aa;
    min-height: 52px;
    border-radius: 9px;
    margin: 3px;
    border: 1px solid #b8c4d8;
}
QScrollBar#MarketTableScroll::handle:vertical:hover {
    background-color: #4a9eff;
    border-color: #8ec0ff;
}
QScrollBar#MarketTableScroll::handle:vertical:pressed {
    background-color: #2a6fbf;
    border-color: #4a9eff;
}
QScrollBar#MarketTableScroll:vertical:disabled {
    background-color: #32323c;
}
QScrollBar#MarketTableScroll::handle:vertical:disabled {
    background-color: #5a5a68;
    border-color: #6a6a78;
}
QScrollBar#MarketTableScroll::add-line:vertical,
QScrollBar#MarketTableScroll::sub-line:vertical {
    background: none;
    height: 0;
}
QScrollBar#MarketTableScroll::add-page:vertical,
QScrollBar#MarketTableScroll::sub-page:vertical {
    background: #2d2d38;
}
"""


class MarketTableHost(QtWidgets.QWidget):
    """行情表格容器：可选右侧独立滚动条 + 加载遮罩。"""

    def __init__(
        self,
        table: QtWidgets.QTableView,
        parent: QtWidgets.QWidget | None = None,
        *,
        external_scrollbar: bool = True,
    ) -> None:
        super().__init__(parent)
        self._table = table
        self._external_scrollbar = external_scrollbar

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(table, stretch=1)

        self._scroll: QtWidgets.QScrollBar | None = None
        if external_scrollbar:
            table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            table.setStyleSheet(_HIDE_TABLE_SCROLLBAR_QSS)

            self._scroll = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Vertical, self)
            self._scroll.setObjectName("MarketTableScroll")
            self._scroll.setFixedWidth(18)
            self._scroll.setStyleSheet(_MARKET_SCROLL_RAIL_QSS)
            body.addWidget(self._scroll)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(body)

        if self._scroll is not None:
            table_bar = table.verticalScrollBar()
            table_bar.valueChanged.connect(self._sync_scroll_to_rail)
            table_bar.rangeChanged.connect(self._sync_scroll_range)
            self._scroll.valueChanged.connect(self._sync_scroll_to_table)
            model = table.model()
            if model is not None:
                model.modelReset.connect(self._schedule_refresh_scrollbar)
                model.rowsInserted.connect(self._schedule_refresh_scrollbar)
                model.rowsRemoved.connect(self._schedule_refresh_scrollbar)
            self._schedule_refresh_scrollbar()

        self._overlay = QtWidgets.QWidget(self)
        self._overlay.setObjectName("MarketTableLoading")
        self._overlay.hide()

        overlay_layout = QtWidgets.QVBoxLayout(self._overlay)
        overlay_layout.setContentsMargins(24, 24, 24, 24)
        overlay_layout.addStretch(1)

        center_row = QtWidgets.QHBoxLayout()
        center_row.addStretch(1)

        panel = QtWidgets.QWidget()
        panel.setObjectName("MarketTableLoadingPanel")
        panel_layout = QtWidgets.QVBoxLayout(panel)
        panel_layout.setContentsMargins(28, 22, 28, 22)
        panel_layout.setSpacing(12)

        self._progress = QtWidgets.QProgressBar()
        self._progress.setObjectName("MarketTableLoadingBar")
        self._progress.setRange(0, 0)
        self._progress.setFixedWidth(220)

        self._label = QtWidgets.QLabel("正在加载…")
        self._label.setObjectName("MarketTableLoadingLabel")
        self._label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        panel_layout.addWidget(self._progress, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        panel_layout.addWidget(self._label)

        center_row.addWidget(panel)
        center_row.addStretch(1)
        overlay_layout.addLayout(center_row)
        overlay_layout.addStretch(1)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[name-defined]
        super().resizeEvent(event)
        self._overlay.setGeometry(self.rect())
        self._schedule_refresh_scrollbar()

    def refresh_scrollbar(self) -> None:
        """表格行数或视口变化后，同步右侧滚动条范围。"""
        if self._scroll is None:
            return
        table_bar = self._table.verticalScrollBar()
        self._table.updateGeometry()
        self._sync_scroll_range(table_bar.minimum(), table_bar.maximum())
        self._sync_scroll_to_rail(table_bar.value())
        has_scroll = table_bar.maximum() > table_bar.minimum()
        self._scroll.setEnabled(has_scroll)
        self._scroll.setVisible(True)

    def _schedule_refresh_scrollbar(self, *_args: object) -> None:
        if self._scroll is None:
            return
        QtCore.QTimer.singleShot(0, self.refresh_scrollbar)

    def show_loading(self, text: str) -> None:
        self._label.setText(text)
        self._overlay.setGeometry(self.rect())
        self._overlay.raise_()
        self._overlay.show()

    def hide_loading(self) -> None:
        self._overlay.hide()

    def _sync_scroll_range(self, minimum: int, maximum: int) -> None:
        if self._scroll is None:
            return
        table_bar = self._table.verticalScrollBar()
        self._scroll.setRange(minimum, maximum)
        self._scroll.setPageStep(max(table_bar.pageStep(), 1))
        self._scroll.setSingleStep(max(table_bar.singleStep(), 1))

    def _sync_scroll_to_rail(self, value: int) -> None:
        if self._scroll is None:
            return
        self._scroll.blockSignals(True)
        self._scroll.setValue(value)
        self._scroll.blockSignals(False)

    def _sync_scroll_to_table(self, value: int) -> None:
        if self._scroll is None:
            return
        table_bar = self._table.verticalScrollBar()
        table_bar.blockSignals(True)
        table_bar.setValue(value)
        table_bar.blockSignals(False)
