"""自选多维看盘后台 Worker。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.quotes.watchlist_multiview.sparkline_data import SparklineMode, load_watchlist_sparklines


class WatchlistMultiSparklineWorker(QtCore.QThread):
    """批量加载自选池迷你图（跟随右侧图表 Tab）。"""

    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        items: list[StockItem],
        *,
        mode: SparklineMode,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._items = list(items)
        self._mode = mode

    def run(self) -> None:
        try:
            kind, payload = load_watchlist_sparklines(self._items, mode=self._mode)
            self.finished.emit({"kind": kind, "points": payload})
        except Exception as ex:
            self.failed.emit(str(ex))
