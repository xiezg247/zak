"""本地 K 线加载与断层检查 Worker。"""

from __future__ import annotations

from vnpy.trader.constant import Interval
from vnpy.trader.database import get_database
from vnpy.trader.ui import QtCore

from vnpy_ashare.data.bar_access import get_scope_overview
from vnpy_ashare.data.bar_health import BarMeta, inspect_bar_gaps
from vnpy_ashare.data.pattern_bars import load_daily_bars_tail, load_scope_bars_tail
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.domain.time.calendar import last_trading_day
from vnpy_ashare.ui.quotes.page.config import LOCAL_CHART_DAILY_LOOKBACK_BARS, LOCAL_CHART_MINUTE_LOOKBACK_BARS
from vnpy_ashare.ui.quotes.workers.quotes_workers.models import LoadedBars


class BarsLoadWorker(QtCore.QThread):
    """加载单标的日 K 尾部窗口（本地图表）。"""

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

            bars = load_daily_bars_tail(
                self.item.symbol,
                self.item.exchange,
                lookback_bars=LOCAL_CHART_DAILY_LOOKBACK_BARS,
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
    """加载单标的指定 scope 尾部 K 线（本地图表）。"""

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

            bars = load_scope_bars_tail(
                self.item.symbol,
                self.item.exchange,
                self.scope,
                lookback_bars=LOCAL_CHART_MINUTE_LOOKBACK_BARS,
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
