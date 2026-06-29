"""策略监控页中部：上下文条 + 信号/持仓纵向分栏。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.quotes.features.watchlist.context_bar import WatchlistPoolContextBar
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_ashare.ui.quotes.watchlist_positions.panel import WatchlistPositionPanel
from vnpy_ashare.ui.quotes.watchlist_signals.panel import WatchlistSignalPanel
from vnpy_ashare.ui.quotes.watchlist_signals.splitter import (
    bind_center_splitter_persistence,
    configure_center_splitter,
    restore_center_splitter,
)


def build_strategy_monitor_center_layout(page: WatchlistHost, center_layout: QtWidgets.QVBoxLayout) -> None:
    page.watchlist_pool_context_bar = WatchlistPoolContextBar(page)
    center_layout.addWidget(page.watchlist_pool_context_bar)

    center_split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
    configure_center_splitter(center_split)
    page.signal_panel = WatchlistSignalPanel(page)
    page.position_panel = WatchlistPositionPanel(page)
    center_split.addWidget(page.signal_panel)
    center_split.addWidget(page.position_panel)
    center_split.setStretchFactor(0, 1)
    center_split.setStretchFactor(1, 1)
    page._center_splitter = center_split
    center_layout.addWidget(center_split, stretch=1)

    bind_center_splitter_persistence(page)
    page._wire_signal_panel()
    page._wire_position_panel()
    QtCore.QTimer.singleShot(0, lambda: restore_center_splitter(page))
