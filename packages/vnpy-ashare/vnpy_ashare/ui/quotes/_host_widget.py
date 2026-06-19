"""WatchlistHost → QWidget 窄转换（避免 quotes_page 循环 import）。"""

from __future__ import annotations

from typing import cast

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost


def as_qwidget(page: WatchlistHost) -> QtWidgets.QWidget:
    return cast(QtWidgets.QWidget, page)
