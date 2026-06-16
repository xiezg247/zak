"""自选多维看盘后台 Worker。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.quotes.watchlist_multiview.sparkline_data import load_watchlist_sparklines


class WatchlistMultiSparklineWorker(QtCore.QThread):
    """批量加载自选池迷你图（交易时段优先分时，否则日 K）。"""

    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        items: list[StockItem],
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._items = list(items)

    def run(self) -> None:
        try:
            kind, payload = load_watchlist_sparklines(self._items)
            self.finished.emit({"kind": kind, "points": payload})
        except Exception as ex:
            self.failed.emit(str(ex))
