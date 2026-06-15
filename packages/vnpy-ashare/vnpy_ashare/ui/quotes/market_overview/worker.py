"""大盘概览加载 Worker。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.quotes.market.market_overview_loaders import load_market_overview


class MarketOverviewLoadWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def run(self) -> None:
        try:
            self.finished.emit(load_market_overview())
        except Exception as ex:
            self.failed.emit(str(ex))
