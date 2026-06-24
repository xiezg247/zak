"""无效日 K 概览清理 Worker。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.data.bars import cleanup_invalid_daily_bars


class InvalidBarCleanupWorker(QtCore.QThread):
    """后台清理无效日 K 概览（避免本地页 activate 阻塞 UI）。"""

    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def run(self) -> None:
        try:
            self.finished.emit(cleanup_invalid_daily_bars())
        except Exception as ex:
            self.failed.emit(str(ex))
