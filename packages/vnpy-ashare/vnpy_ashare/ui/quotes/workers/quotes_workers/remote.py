"""TickFlow / Redis 行情与远端 K 线 Worker。"""

from __future__ import annotations

from typing import Literal

from vnpy.trader.ui import QtCore

from vnpy_ashare.data.bar_access import get_period_overview, load_period_bars
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.integrations.tickflow.depth import DepthPermissionError, fetch_depth_from_tickflow
from vnpy_ashare.integrations.tickflow.klines import fetch_intraday_bars, fetch_minute_bars
from vnpy_ashare.integrations.tickflow.quotes import fetch_index_ticker
from vnpy_ashare.quotes.core.provider import QuoteSource, fetch_quotes
from vnpy_ashare.ui.quotes.chart.minute_bars import LIVE_MINUTE_TAIL_COUNT
from vnpy_ashare.ui.quotes.workers.quotes_workers.models import LoadedPeriodBars


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


class IndexQuotesWorker(QtCore.QThread):
    """拉取大盘指数 ticker。"""

    finished = QtCore.Signal(list)
    failed = QtCore.Signal(str)

    def run(self) -> None:
        try:
            self.finished.emit(fetch_index_ticker())
        except Exception as ex:
            self.failed.emit(str(ex))
