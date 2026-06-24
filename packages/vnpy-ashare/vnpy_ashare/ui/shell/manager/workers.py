"""数据管理页后台任务。"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import Field
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore

from vnpy_ashare.app.engine_access import get_bar_service
from vnpy_ashare.data.minute_periods import bar_interval, is_daily_scope
from vnpy_ashare.services.bar import build_symbol_name_map, iter_bar_overviews
from vnpy_common.domain.base import FrozenModel


class OverviewRow(FrozenModel):
    symbol: str = Field(description="六位股票代码")
    exchange: Exchange = Field(description="交易所代码")
    period: str = Field(description="K 线周期")
    count: int = Field(description="数量")
    start: datetime = Field(description="开始日期")
    end: datetime = Field(description="结束日期")
    stock_name: str = Field(description="证券简称")
    interval: Interval = Field(description="VeighNa K 线周期枚举")


class TreeRefreshPayload(FrozenModel):
    rows: list[OverviewRow] = Field(description="数据行列表")


def _overview_group_key(period: str) -> str:
    if is_daily_scope(period):
        return "daily"
    return period


def _collect_tree_rows(main_engine: MainEngine | None) -> TreeRefreshPayload:
    bar_svc = get_bar_service(main_engine)
    name_map = bar_svc.build_symbol_name_map() if bar_svc else build_symbol_name_map()
    rows: list[OverviewRow] = []
    seen: set[tuple[str, Exchange, str]] = set()

    for scope in ("daily", "1m"):
        overviews = bar_svc.iter_overviews(scope) if bar_svc else iter_bar_overviews(scope=scope)
        for overview in overviews:
            dedupe_key = (overview.symbol, overview.exchange, overview.period)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            if _overview_group_key(overview.period) not in ("daily", "1m"):
                continue
            interval = Interval.DAILY if is_daily_scope(overview.period) else bar_interval(overview.period)
            rows.append(
                OverviewRow(
                    symbol=overview.symbol,
                    exchange=overview.exchange,
                    period=overview.period,
                    count=overview.count,
                    start=overview.start,
                    end=overview.end,
                    stock_name=name_map.get((overview.symbol, overview.exchange), ""),
                    interval=interval,
                )
            )
    return TreeRefreshPayload(rows=rows)


class TreeRefreshWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, main_engine: MainEngine | None) -> None:
        super().__init__()
        self._main_engine = main_engine
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            payload = _collect_tree_rows(self._main_engine)
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.finished.emit(payload)
        except Exception as ex:
            self.failed.emit(str(ex))


class _BarDatabaseEngine(Protocol):
    def load_bar_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime,
    ) -> list: ...

    def output_data_to_csv(
        self,
        path: str,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime,
    ) -> bool: ...

    def delete_bar_data(self, symbol: str, exchange: Exchange, interval: Interval) -> int: ...


class LoadBarsWorker(QtCore.QThread):
    finished = QtCore.Signal(list)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        engine: _BarDatabaseEngine,
        *,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime,
    ) -> None:
        super().__init__()
        self._engine = engine
        self._symbol = symbol
        self._exchange = exchange
        self._interval = interval
        self._start = start
        self._end = end
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            bars = self._engine.load_bar_data(
                self._symbol,
                self._exchange,
                self._interval,
                self._start,
                self._end,
            )
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.finished.emit(bars)
        except Exception as ex:
            self.failed.emit(str(ex))


class ExportCsvWorker(QtCore.QThread):
    finished = QtCore.Signal(bool)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        engine: _BarDatabaseEngine,
        *,
        path: str,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime,
    ) -> None:
        super().__init__()
        self._engine = engine
        self._path = path
        self._symbol = symbol
        self._exchange = exchange
        self._interval = interval
        self._start = start
        self._end = end
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            ok = self._engine.output_data_to_csv(
                self._path,
                self._symbol,
                self._exchange,
                self._interval,
                self._start,
                self._end,
            )
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.finished.emit(ok)
        except Exception as ex:
            self.failed.emit(str(ex))


class DeleteBarsWorker(QtCore.QThread):
    finished = QtCore.Signal(int)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        engine: _BarDatabaseEngine,
        *,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
    ) -> None:
        super().__init__()
        self._engine = engine
        self._symbol = symbol
        self._exchange = exchange
        self._interval = interval

    def run(self) -> None:
        try:
            count = self._engine.delete_bar_data(self._symbol, self._exchange, self._interval)
            self.finished.emit(count)
        except Exception as ex:
            self.failed.emit(str(ex))
