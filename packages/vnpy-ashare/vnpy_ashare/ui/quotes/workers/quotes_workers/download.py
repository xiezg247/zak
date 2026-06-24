"""日 K / 分 K 下载 Worker。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from vnpy.trader.constant import Interval
from vnpy.trader.ui import QtCore

from vnpy_ashare.data.bar_access import get_scope_overview
from vnpy_ashare.data.bars import default_minute_download_start, download_bars, download_period_bars
from vnpy_ashare.data.minute_periods import period_step
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.ui.quotes.workers.quotes_workers.log import emit_worker_log
from vnpy_ashare.ui.quotes.workers.quotes_workers.models import FULL_BAR_START


class DownloadWorker(QtCore.QThread):
    """下载单标的日 K（full / incremental）。"""

    finished = QtCore.Signal(int)
    failed = QtCore.Signal(str)
    log = QtCore.Signal(str)

    def __init__(
        self,
        item: StockItem,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        mode: Literal["full", "incremental"] = "full",
    ) -> None:
        super().__init__()
        self.item = item
        self.start_dt = start
        self.end_dt = end
        self.mode = mode
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            start = self.start_dt
            end = self.end_dt or datetime.now()
            if self.mode == "incremental" and start is None:
                overview = get_scope_overview(
                    self.item.symbol,
                    self.item.exchange,
                    "daily",
                )
                if overview is None:
                    raise RuntimeError("无本地数据，请先下载")
                start = overview.end + timedelta(days=1)
                if start.date() > end.date():
                    emit_worker_log(self.log, "已是最新，无新增 K 线")
                    self.finished.emit(0)
                    return
            if start is None:
                start = FULL_BAR_START

            emit_worker_log(self.log, f"下载区间 {start.date()} ~ {end.date()}")
            count = download_bars(
                symbol=self.item.symbol,
                exchange=self.item.exchange,
                interval=Interval.DAILY,
                start=start,
                end=end,
                output=lambda msg: emit_worker_log(self.log, msg),
            )
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.finished.emit(count)
        except Exception as ex:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.failed.emit(str(ex))


class MinuteDownloadWorker(QtCore.QThread):
    """下载单标的分 K（1m / 5m 等）。"""

    finished = QtCore.Signal(int)
    failed = QtCore.Signal(str)
    log = QtCore.Signal(str)

    def __init__(
        self,
        item: StockItem,
        *,
        period: str,
        start: datetime | None = None,
        end: datetime | None = None,
        mode: Literal["full", "incremental"] = "full",
    ) -> None:
        super().__init__()
        self.item = item
        self.period = period
        self.start_dt = start
        self.end_dt = end
        self.mode = mode
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            end = self.end_dt or datetime.now()
            start = self.start_dt
            if self.mode == "incremental" and start is None:
                overview = get_scope_overview(
                    self.item.symbol,
                    self.item.exchange,
                    self.period,
                )
                if overview is None:
                    raise RuntimeError("无本地数据，请先下载")
                start = overview.end + period_step(self.period)
                if start >= end:
                    emit_worker_log(self.log, "已是最新，无新增 K 线")
                    self.finished.emit(0)
                    return
            if start is None:
                start = default_minute_download_start(end)

            emit_worker_log(self.log, f"下载区间 {start} ~ {end}")
            count = download_period_bars(
                symbol=self.item.symbol,
                exchange=self.item.exchange,
                period=self.period,
                start=start,
                end=end,
                output=lambda msg: emit_worker_log(self.log, msg),
            )
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.finished.emit(count)
        except Exception as ex:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.failed.emit(str(ex))
