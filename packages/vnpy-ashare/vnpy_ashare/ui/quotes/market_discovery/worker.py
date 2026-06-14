"""市场页异动带后台加载。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.quotes.radar_loaders import load_radar_card


class MarketDiscoveryLoadWorker(QtCore.QThread):
    """并行加载放量/资金异动（复用雷达 discovery loader）。"""

    finished = QtCore.Signal(object, object)
    failed = QtCore.Signal(str)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._cancelled = False

    def request_cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        if self._cancelled:
            return
        try:
            volume = load_radar_card("discovery_volume_surge")
            if self._cancelled:
                return
            moneyflow = load_radar_card("discovery_moneyflow_intraday")
        except Exception as ex:
            self.failed.emit(str(ex))
            return
        if self._cancelled:
            return
        self.finished.emit(volume, moneyflow)
