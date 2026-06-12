"""市场页表格加载遮罩。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_common.ui.loading_overlay import ContentLoadingOverlay
from vnpy_common.ui.scroll_area import MARKET_TABLE_SCROLL_BAR

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
            self._scroll.setObjectName(MARKET_TABLE_SCROLL_BAR)
            self._scroll.setFixedWidth(18)
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

        self._overlay = ContentLoadingOverlay(self)

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
        self._overlay.show_loading(text)
        self._overlay.setGeometry(self.rect())
        self._overlay.raise_()

    def hide_loading(self) -> None:
        self._overlay.hide_loading()

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
