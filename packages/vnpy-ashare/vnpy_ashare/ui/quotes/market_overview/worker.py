"""大盘概览加载 Worker。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.quotes.market.market_overview_loaders import load_market_overview


class MarketOverviewLoadWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        *,
        intraday: bool = True,
        force: bool = False,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._intraday = intraday
        self._force = force
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            data = load_market_overview(intraday=self._intraday, force=self._force)
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.finished.emit(data)
        except Exception as ex:
            self.failed.emit(str(ex))
