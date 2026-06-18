"""后台补全关注池 1m K（批量回测预检等）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.jobs.bars.focus_pool_minute import batch_fill_focus_pool_minute_bars
from vnpy_ashare.services.focus_pool import stock_items_from_vt_symbols


class FocusPoolMinuteFillWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)
    log = QtCore.Signal(str)

    def __init__(self, vt_symbols: list[str]) -> None:
        super().__init__()
        self._vt_symbols = vt_symbols

    def run(self) -> None:
        try:
            items = stock_items_from_vt_symbols(self._vt_symbols)
            if not items:
                self.failed.emit("无有效标的")
                return

            def on_progress(progress) -> None:
                self.log.emit(f"{progress.current}/{progress.total} {progress.label}")

            result = batch_fill_focus_pool_minute_bars(items, delay=0.5, progress=on_progress)
            self.finished.emit(result)
        except Exception as ex:
            self.failed.emit(str(ex) or "1m K 补全失败")
