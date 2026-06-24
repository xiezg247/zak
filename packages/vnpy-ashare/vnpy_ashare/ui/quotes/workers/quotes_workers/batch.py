"""批量补全 / 断层修复 Worker。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange
from vnpy.trader.ui import QtCore

from vnpy_ashare.data.bar_health import BarMeta
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.jobs.bars.local_fill import batch_fill_gap_daily_bars, batch_fill_stale_daily_bars


class BatchGapFillWorker(QtCore.QThread):
    """批量补全日 K 内部断层（batch_fill_gap_daily_bars）。"""

    progress = QtCore.Signal(object)
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        items: list[StockItem],
        bar_meta: dict[tuple[str, Exchange], BarMeta],
        *,
        delay: float = 0.3,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.items = items
        self.bar_meta = bar_meta
        self.delay = delay
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            result = batch_fill_gap_daily_bars(
                self.items,
                self.bar_meta,
                delay=self.delay,
                progress=lambda item: self.progress.emit(item),
                should_cancel=lambda: self._cancel_requested,
            )
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.finished.emit(result)
        except Exception as ex:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.failed.emit(str(ex))


class BatchFillWorker(QtCore.QThread):
    """批量补全过期日 K（batch_fill_stale_daily_bars）。"""

    progress = QtCore.Signal(object)
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        items: list[StockItem],
        bar_meta: dict[tuple[str, Exchange], BarMeta],
        *,
        delay: float = 0.3,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.items = items
        self.bar_meta = bar_meta
        self.delay = delay
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            result = batch_fill_stale_daily_bars(
                self.items,
                self.bar_meta,
                delay=self.delay,
                progress=lambda item: self.progress.emit(item),
                should_cancel=lambda: self._cancel_requested,
            )
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.finished.emit(result)
        except Exception as ex:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.failed.emit(str(ex))
