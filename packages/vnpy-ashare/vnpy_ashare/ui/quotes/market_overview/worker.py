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

    def run(self) -> None:
        try:
            self.finished.emit(load_market_overview(intraday=self._intraday, force=self._force))
        except Exception as ex:
            self.failed.emit(str(ex))
