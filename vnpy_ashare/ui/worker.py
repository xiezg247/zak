from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from vnpy.trader.constant import Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import BarData
from vnpy.trader.ui import QtCore

from vnpy_ashare.app_db import search_universe, load_universe_page
from vnpy_ashare.bar_health import BarMeta, inspect_bar_gaps
from vnpy_ashare.bar_store import get_period_overview, get_scope_overview, load_period_bars, load_scope_bars
from vnpy_ashare.minute_periods import is_daily_scope, period_step
from vnpy_ashare.bars import (
    default_minute_download_start,
    download_bars,
    download_period_bars,
    load_downloaded_stocks,
    load_watchlist,
)
from vnpy_ashare.calendar import last_trading_day
from vnpy_ashare.models import StockItem
from vnpy_ashare.quotes.depth_client import DepthPermissionError, fetch_depth_from_tickflow
from vnpy_ashare.quotes.depth_snapshot import DepthSnapshot
from vnpy_ashare.quotes import QuoteSnapshot, QuoteSource, fetch_index_ticker, fetch_quotes
from vnpy_ashare.quotes.provider import get_redis_provider
from vnpy_ashare.tickflow_klines import fetch_intraday_bars, fetch_minute_bars
from vnpy_ashare.universe import load_universe, sync_universe


@dataclass
class MarketPageResult:
    items: list[StockItem]
    quotes: dict[str, QuoteSnapshot]
    total: int
    page: int
    page_size: int
    mode: str
    updated_at: str | None = None


@dataclass
class LoadedBars:
    item: StockItem
    bars: list[BarData]
    start: datetime
    end: datetime


@dataclass
class LoadedPeriodBars:
    bars: list[BarData]
    from_local: bool
    period: str
    start: datetime | None = None
    end: datetime | None = None


class UniverseLoadWorker(QtCore.QThread):
    finished = QtCore.Signal(list)
    failed = QtCore.Signal(str)

    def __init__(self, scope: str, *, local_scope: str = "daily") -> None:
        super().__init__()
        self.scope = scope
        self.local_scope = local_scope

    def run(self) -> None:
        try:
            if self.scope == "全部A股":
                stocks = load_universe(allow_sync=False)
            elif self.scope == "自选池":
                stocks = load_watchlist()
            else:
                stocks = load_downloaded_stocks(scope=self.local_scope)
            self.finished.emit(stocks)
        except Exception as ex:
            self.failed.emit(str(ex))


class UniverseSyncWorker(QtCore.QThread):
    finished = QtCore.Signal(str)
    failed = QtCore.Signal(str)

    def run(self) -> None:
        try:
            path = sync_universe(force=True)
            self.finished.emit(str(path))
        except Exception as ex:
            self.failed.emit(str(ex))


class BarsLoadWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, item: StockItem) -> None:
        super().__init__()
        self.item = item

    def run(self) -> None:
        try:
            overview = get_scope_overview(
                self.item.symbol,
                self.item.exchange,
                "daily",
            )
            if not overview:
                self.finished.emit(None)
                return

            bars = load_scope_bars(
                self.item.symbol,
                self.item.exchange,
                "daily",
                overview.start,
                overview.end,
            )
            result = LoadedBars(
                item=self.item,
                bars=bars,
                start=overview.start,
                end=overview.end,
            )
            self.finished.emit(result)
        except Exception as ex:
            self.failed.emit(str(ex))


class ScopeBarsLoadWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, item: StockItem, *, scope: str) -> None:
        super().__init__()
        self.item = item
        self.scope = scope

    def run(self) -> None:
        try:
            overview = get_scope_overview(
                self.item.symbol,
                self.item.exchange,
                self.scope,
            )
            if overview is None:
                self.finished.emit(None)
                return

            bars = load_scope_bars(
                self.item.symbol,
                self.item.exchange,
                self.scope,
                overview.start,
                overview.end,
            )
            result = LoadedBars(
                item=self.item,
                bars=bars,
                start=overview.start,
                end=overview.end,
            )
            self.finished.emit(result)
        except Exception as ex:
            self.failed.emit(str(ex))


FULL_BAR_START = datetime(2020, 1, 1)


class DownloadWorker(QtCore.QThread):
    finished = QtCore.Signal(int)
    failed = QtCore.Signal(str)

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

    def run(self) -> None:
        try:
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
                    self.finished.emit(0)
                    return
            if start is None:
                start = FULL_BAR_START

            count = download_bars(
                symbol=self.item.symbol,
                exchange=self.item.exchange,
                interval=Interval.DAILY,
                start=start,
                end=end,
                output=lambda _msg: None,
            )
            self.finished.emit(count)
        except Exception as ex:
            self.failed.emit(str(ex))


class MinuteDownloadWorker(QtCore.QThread):
    finished = QtCore.Signal(int)
    failed = QtCore.Signal(str)

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

    def run(self) -> None:
        try:
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
                    self.finished.emit(0)
                    return
            if start is None:
                start = default_minute_download_start(end)

            count = download_period_bars(
                symbol=self.item.symbol,
                exchange=self.item.exchange,
                period=self.period,
                start=start,
                end=end,
                output=lambda _msg: None,
            )
            self.finished.emit(count)
        except Exception as ex:
            self.failed.emit(str(ex))


class BarGapCheckWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, item: StockItem, meta: BarMeta) -> None:
        super().__init__()
        self.item = item
        self.meta = meta

    def run(self) -> None:
        try:
            database = get_database()
            bars = database.load_bar_data(
                self.item.symbol,
                self.item.exchange,
                Interval.DAILY,
                self.meta.start,
                self.meta.end,
            )
            bar_dates = {bar.datetime.date() for bar in bars}
            result = inspect_bar_gaps(
                self.meta,
                bar_dates,
                as_of=last_trading_day(),
            )
            self.finished.emit((self.item, result))
        except Exception as ex:
            self.failed.emit(str(ex))


class QuotesRefreshWorker(QtCore.QThread):
    finished = QtCore.Signal(dict)
    failed = QtCore.Signal(str)

    def __init__(self, items: list[StockItem], quote_source: QuoteSource) -> None:
        super().__init__()
        self.items = items
        self.quote_source = quote_source

    def run(self) -> None:
        try:
            quotes = fetch_quotes(self.items, self.quote_source)
            self.finished.emit(quotes)
        except Exception as ex:
            self.failed.emit(str(ex))


class IntradayBarsWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, item: StockItem) -> None:
        super().__init__()
        self.item = item

    def run(self) -> None:
        try:
            bars = fetch_intraday_bars(self.item)
            self.finished.emit(bars)
        except Exception as ex:
            self.failed.emit(str(ex))


class MinuteBarsWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, item: StockItem, *, period: str = "1m") -> None:
        super().__init__()
        self.item = item
        self.period = period

    def run(self) -> None:
        try:
            overview = get_period_overview(
                self.item.symbol,
                self.item.exchange,
                self.period,
            )
            if overview is not None:
                bars = load_period_bars(
                    self.item.symbol,
                    self.item.exchange,
                    self.period,
                    overview.start,
                    overview.end,
                )
                if bars:
                    self.finished.emit(
                        LoadedPeriodBars(
                            bars=bars,
                            from_local=True,
                            period=self.period,
                            start=overview.start,
                            end=overview.end,
                        )
                    )
                    return

            bars = fetch_minute_bars(self.item, period=self.period)
            self.finished.emit(
                LoadedPeriodBars(
                    bars=bars,
                    from_local=False,
                    period=self.period,
                )
            )
        except Exception as ex:
            self.failed.emit(str(ex))


class DepthRefreshWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    permission_denied = QtCore.Signal(str)
    failed = QtCore.Signal(str)

    def __init__(self, item: StockItem) -> None:
        super().__init__()
        self.item = item

    def run(self) -> None:
        try:
            depth = fetch_depth_from_tickflow(self.item)
            self.finished.emit(depth)
        except DepthPermissionError as ex:
            self.permission_denied.emit(str(ex))
        except Exception as ex:
            self.failed.emit(str(ex))


class MarketPageLoadWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        *,
        keyword: str,
        page: int,
        page_size: int,
    ) -> None:
        super().__init__()
        self.keyword = keyword.strip()
        self.page = max(page, 0)
        self.page_size = page_size

    def run(self) -> None:
        try:
            provider = get_redis_provider()
            offset = self.page * self.page_size
            updated_at: str | None = None

            updated_at = provider.updated_at()

            if self.keyword:
                rows, total = search_universe(
                    self.keyword,
                    limit=self.page_size,
                    offset=offset,
                )
                items = [
                    StockItem(symbol=symbol, exchange=exchange, name=name)
                    for symbol, exchange, name in rows
                ]
                quotes = provider.get_quotes(items)
                mode = "search"
            else:
                rows, total = load_universe_page(
                    offset=offset,
                    limit=self.page_size,
                )
                items = [
                    StockItem(symbol=symbol, exchange=exchange, name=name)
                    for symbol, exchange, name in rows
                ]
                quotes = provider.get_quotes(items)
                mode = "list"

            self.finished.emit(
                MarketPageResult(
                    items=items,
                    quotes=quotes,
                    total=total,
                    page=self.page,
                    page_size=self.page_size,
                    mode=mode,
                    updated_at=updated_at,
                )
            )
        except Exception as ex:
            self.failed.emit(str(ex))


class IndexQuotesWorker(QtCore.QThread):
    finished = QtCore.Signal(list)
    failed = QtCore.Signal(str)

    def run(self) -> None:
        try:
            self.finished.emit(fetch_index_ticker())
        except Exception as ex:
            self.failed.emit(str(ex))


def _load_downloaded() -> list[StockItem]:
    return load_downloaded_stocks()


@dataclass
class ScreenerRunResult:
    """GUI Worker 结果（与 screener.runner.ScreenerRunResult 结构一致）。"""

    rows: list[dict]
    condition: str
    updated_at: str | None
    total_scanned: int
    source: str = "quote"
    columns: list[tuple[str, str]] | None = None

    @classmethod
    def from_runner(cls, result) -> ScreenerRunResult:
        return cls(
            rows=result.rows,
            condition=result.condition,
            updated_at=result.updated_at,
            total_scanned=result.total_scanned,
            source=result.source,
            columns=result.columns,
        )


class ScreenerRunWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        *,
        preset: str,
        top_n: int,
        min_change_pct: float | None = None,
        max_change_pct: float | None = None,
        min_turnover: float | None = None,
        scheme_id: str | None = None,
    ) -> None:
        super().__init__()
        self.preset = preset
        self.top_n = top_n
        self.min_change_pct = min_change_pct
        self.max_change_pct = max_change_pct
        self.min_turnover = min_turnover
        self.scheme_id = scheme_id

    def run(self) -> None:
        try:
            from vnpy_ashare.screener.runner import ScreenerRequest, run_screener, resolve_preset_input

            if self.scheme_id:
                request = ScreenerRequest(
                    preset="",
                    top_n=self.top_n,
                    scheme_id=self.scheme_id,
                )
            elif self.preset.startswith("我的 · "):
                request = resolve_preset_input(self.preset)
                request.top_n = self.top_n
            else:
                request = ScreenerRequest(
                    preset=self.preset,
                    top_n=self.top_n,
                    min_change_pct=self.min_change_pct,
                    max_change_pct=self.max_change_pct,
                    min_turnover=self.min_turnover,
                )
            result = run_screener(request)
            self.finished.emit(ScreenerRunResult.from_runner(result))
        except Exception as ex:
            self.failed.emit(str(ex))


class ScreenerBatchDownloadWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, rows: list[dict], parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.rows = rows

    def run(self) -> None:
        try:
            from vnpy_ashare.screener.batch_actions import batch_download_daily_bars

            result = batch_download_daily_bars(self.rows)
            self.finished.emit(result)
        except Exception as ex:
            self.failed.emit(str(ex))


class ScreenerBatchBacktestWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        main_engine,
        rows: list[dict],
        params,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.main_engine = main_engine
        self.rows = rows
        self.params = params

    def run(self) -> None:
        try:
            from vnpy_ashare.screener.batch_actions import run_batch_backtests

            results = run_batch_backtests(self.main_engine, self.rows, self.params)
            self.finished.emit(results)
        except Exception as ex:
            self.failed.emit(str(ex))
