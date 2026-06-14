"""看盘页 Qt Worker（从 ui.worker 迁出）。

读 K 线 / universe → bar_access；下载与同步 → bars / universe（写路径）。
各 Worker 在后台线程运行，通过 Signal 回传 GUI 线程。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import BarData
from vnpy.trader.ui import QtCore

from vnpy_ashare.data.bar_access import (
    get_period_overview,
    get_scope_overview,
    load_period_bars,
    load_scope_bars,
    load_universe_page,
    load_universe_rows,
    load_universe_slice,
    search_universe,
)
from vnpy_ashare.data.bar_health import BarMeta, inspect_bar_gaps
from vnpy_ashare.data.bars import (
    count_downloaded_stocks,
    default_minute_download_start,
    download_bars,
    download_period_bars,
    load_downloaded_stocks,
    load_downloaded_stocks_page,
    load_watchlist,
)
from vnpy_ashare.data.minute_periods import period_step
from vnpy_ashare.domain.calendar import last_trading_day
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.integrations.tickflow import (
    DepthPermissionError,
    fetch_depth_from_tickflow,
    fetch_intraday_bars,
    fetch_minute_bars,
)
from vnpy_ashare.jobs.local_fill import batch_fill_gap_daily_bars, batch_fill_stale_daily_bars
from vnpy_ashare.quotes import QuoteSnapshot, QuoteSource, fetch_index_ticker, fetch_quotes
from vnpy_ashare.quotes.provider import get_redis_provider
from vnpy_ashare.storage.universe import load_universe, sync_universe
from vnpy_ashare.ui.quotes.chart.minute_bars import LIVE_MINUTE_TAIL_COUNT

# 读 K 线 / universe 列表 → bar_access；下载与同步 → bars / universe（写路径）


@dataclass
class MarketPageResult:
    """市场页分页加载结果（标的 + Redis 行情）。"""

    items: list[StockItem]
    quotes: dict[str, QuoteSnapshot]
    total: int
    page: int
    page_size: int
    mode: str
    updated_at: str | None = None
    board: str | None = None


@dataclass
class MarketFullResult:
    """市场页全量加载结果（涨幅榜序 + Redis 行情）。"""

    items: list[StockItem]
    quotes: dict[str, QuoteSnapshot]
    updated_at: str | None = None


@dataclass
class LoadedBars:
    """日 K 加载结果。"""

    item: StockItem
    bars: list[BarData]
    start: datetime
    end: datetime


@dataclass
class LoadedPeriodBars:
    """分 K 加载结果（本地或 TickFlow 远端）。"""

    bars: list[BarData]
    from_local: bool
    period: str
    start: datetime | None = None
    end: datetime | None = None


FULL_BAR_START = datetime(2020, 1, 1)


def _emit_worker_log(signal: QtCore.Signal, message: object) -> None:
    text = str(message).strip()
    if text:
        signal.emit(text)


class UniverseLoadWorker(QtCore.QThread):
    """加载 universe 列表（全部 A 股 / 自选池 / 已下载）。"""

    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        scope: str,
        *,
        local_scope: str = "daily",
        offset: int = 0,
        limit: int | None = None,
    ) -> None:
        super().__init__()
        self.scope = scope
        self.local_scope = local_scope
        self.offset = max(offset, 0)
        self.limit = limit
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            if self.scope == "全部A股":
                stocks = load_universe(allow_sync=False)
                total = len(stocks)
            elif self.scope == "自选池":
                stocks = load_watchlist()
                total = len(stocks)
            elif self.limit is not None:
                total = count_downloaded_stocks(scope=self.local_scope)
                stocks = load_downloaded_stocks_page(
                    scope=self.local_scope,
                    offset=self.offset,
                    limit=self.limit,
                )
            else:
                stocks = load_downloaded_stocks(scope=self.local_scope)
                total = len(stocks)
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.finished.emit(UniverseLoadResult(items=stocks, total=total))
        except Exception as ex:
            self.failed.emit(str(ex))


@dataclass(frozen=True)
class UniverseLoadResult:
    items: list
    total: int


class UniverseSyncWorker(QtCore.QThread):
    """同步 A 股列表到本地 SQLite。"""

    finished = QtCore.Signal(str)
    failed = QtCore.Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            path = sync_universe(force=True)
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.finished.emit(str(path))
        except Exception as ex:
            self.failed.emit(str(ex))


class BarsLoadWorker(QtCore.QThread):
    """加载单标的日 K（bar_access）。"""

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
    """加载单标的指定 scope（daily / 分 K）K 线。"""

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
                    _emit_worker_log(self.log, "已是最新，无新增 K 线")
                    self.finished.emit(0)
                    return
            if start is None:
                start = FULL_BAR_START

            _emit_worker_log(self.log, f"下载区间 {start.date()} ~ {end.date()}")
            count = download_bars(
                symbol=self.item.symbol,
                exchange=self.item.exchange,
                interval=Interval.DAILY,
                start=start,
                end=end,
                output=lambda msg: _emit_worker_log(self.log, msg),
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
                    _emit_worker_log(self.log, "已是最新，无新增 K 线")
                    self.finished.emit(0)
                    return
            if start is None:
                start = default_minute_download_start(end)

            _emit_worker_log(self.log, f"下载区间 {start} ~ {end}")
            count = download_period_bars(
                symbol=self.item.symbol,
                exchange=self.item.exchange,
                period=self.period,
                start=start,
                end=end,
                output=lambda msg: _emit_worker_log(self.log, msg),
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


class BarGapCheckWorker(QtCore.QThread):
    """选中行异步扫描日 K 断层（inspect_bar_gaps）。"""

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
                symbol=self.item.symbol,
                exchange=self.item.exchange,
            )
            self.finished.emit((self.item, result))
        except Exception as ex:
            self.failed.emit(str(ex))


class QuotesRefreshWorker(QtCore.QThread):
    """批量拉取 TickFlow / Redis 行情快照。"""

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
    """拉取 TickFlow 分时 K 线。"""

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
    """加载分 K：优先本地，无数据时 fallback TickFlow。"""

    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        item: StockItem,
        *,
        period: str = "1m",
        mode: Literal["full", "tail"] = "full",
    ) -> None:
        super().__init__()
        self.item = item
        self.period = period
        self.mode = mode

    def run(self) -> None:
        try:
            if self.mode == "tail":
                bars = fetch_minute_bars(
                    self.item,
                    period=self.period,
                    count=LIVE_MINUTE_TAIL_COUNT,
                )
                self.finished.emit(
                    LoadedPeriodBars(
                        bars=bars,
                        from_local=False,
                        period=self.period,
                    )
                )
                return

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
    """拉取 TickFlow 五档盘口；权限不足时 emission permission_denied。"""

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
    """市场页分页：Redis 涨幅榜或 universe 列表 + 行情。"""

    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        *,
        keyword: str,
        page: int,
        page_size: int,
        board: str | None = None,
        cached_total: int | None = None,
        rank_id: str = "change_pct",
    ) -> None:
        super().__init__()
        self.keyword = keyword.strip()
        self.page = max(page, 0)
        self.page_size = page_size
        self.board = board if board and board != "全部" else None
        self.cached_total = cached_total
        self.rank_id = rank_id
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            provider = get_redis_provider()
            offset = self.page * self.page_size
            updated_at: str | None = provider.updated_at()

            if self.keyword:
                rows, total = search_universe(
                    self.keyword,
                    limit=self.page_size,
                    offset=offset,
                    board=self.board,
                )
                items = [StockItem(symbol=symbol, exchange=exchange, name=name) for symbol, exchange, name in rows]
                quotes = provider.get_quotes(items)
                mode = "search"
            elif self.board is None:
                items, quotes, total = provider.get_rank_page(
                    offset,
                    self.page_size,
                    rank_id=self.rank_id,
                )
                mode = "rank"
            else:
                if self.cached_total is not None:
                    total = self.cached_total
                    rows = load_universe_slice(
                        offset=offset,
                        limit=self.page_size,
                        board=self.board,
                    )
                else:
                    rows, total = load_universe_page(
                        offset=offset,
                        limit=self.page_size,
                        board=self.board,
                    )
                items = [StockItem(symbol=symbol, exchange=exchange, name=name) for symbol, exchange, name in rows]
                quotes = provider.get_quotes(items)
                mode = "list"

            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.finished.emit(
                MarketPageResult(
                    items=items,
                    quotes=quotes,
                    total=total,
                    page=self.page,
                    page_size=self.page_size,
                    mode=mode,
                    updated_at=updated_at,
                    board=self.board,
                )
            )
        except Exception as ex:
            self.failed.emit(str(ex))


class MarketFullLoadWorker(QtCore.QThread):
    """市场/榜单页全量：Redis 指定榜 + 全量行情（无榜时回退 universe）。"""

    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, *, rank_id: str = "change_pct") -> None:
        super().__init__()
        self.rank_id = rank_id
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    @staticmethod
    def _quote_sort_value(quote: QuoteSnapshot | None, spec) -> float:
        from vnpy_ashare.quotes.rank_engine import quote_rank_value

        if quote is None:
            return float("-inf") if not spec.ascending else float("inf")
        return quote_rank_value(quote, spec.sort_column or spec.redis_field)

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            provider = get_redis_provider()
            updated_at: str | None = provider.updated_at()
            store = provider._store
            from vnpy_ashare.quotes.rank_catalog import get_rank_definition

            spec = get_rank_definition(self.rank_id)
            name_map = {(symbol, exchange): name for symbol, exchange, name in load_universe_rows()}

            from vnpy_ashare.quotes.rank_engine import apply_rank_catalog
            from vnpy_ashare.quotes.rank_scope import build_stock_items_from_rank_symbols, load_watchlist_rank_catalog

            if spec.scope == "watchlist":
                tf_symbols, quotes = load_watchlist_rank_catalog(store, spec)
                items = build_stock_items_from_rank_symbols(tf_symbols, quotes, name_map=name_map)
            else:
                tf_symbols = store.list_all_rank_symbols(
                    field=spec.redis_field,
                    ascending=spec.ascending,
                )

                if tf_symbols:
                    quotes = store.get_quotes(tf_symbols)
                    tf_symbols = apply_rank_catalog(tf_symbols, quotes, spec)
                    items = build_stock_items_from_rank_symbols(tf_symbols, quotes, name_map=name_map)
                else:
                    from vnpy_ashare.quotes.rank_engine import quote_matches_rank, rank_needs_post_process

                    items = [StockItem(symbol=symbol, exchange=exchange, name=name) for symbol, exchange, name in load_universe_rows()]
                    quotes = provider.get_quotes(items)
                    if rank_needs_post_process(spec):
                        items = [item for item in items if (quote := quotes.get(item.tickflow_symbol)) is not None and quote_matches_rank(quote, spec)]
                    items.sort(
                        key=lambda stock: self._quote_sort_value(quotes.get(stock.tickflow_symbol), spec),
                        reverse=not spec.ascending,
                    )

            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.finished.emit(
                MarketFullResult(
                    items=items,
                    quotes=quotes,
                    updated_at=updated_at,
                )
            )
        except Exception as ex:
            self.failed.emit(str(ex))


class IndexQuotesWorker(QtCore.QThread):
    """拉取大盘指数 ticker。"""

    finished = QtCore.Signal(list)
    failed = QtCore.Signal(str)

    def run(self) -> None:
        try:
            self.finished.emit(fetch_index_ticker())
        except Exception as ex:
            self.failed.emit(str(ex))


class DiagnoseWorker(QtCore.QThread):
    """后台调用 AnalysisService.diagnose。"""

    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        analysis_service,
        *,
        vt_symbol: str,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.analysis_service = analysis_service
        self.vt_symbol = vt_symbol

    def run(self) -> None:
        try:
            result = self.analysis_service.diagnose(self.vt_symbol)
            self.finished.emit(result)
        except Exception as ex:
            self.failed.emit(str(ex))


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
