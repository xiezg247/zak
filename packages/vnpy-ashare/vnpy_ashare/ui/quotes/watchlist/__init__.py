"""自选页共享类型（Host 协议等）。"""

from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_ashare.ui.quotes.watchlist.pool_host import WatchlistPoolHost
from vnpy_ashare.ui.quotes.watchlist.refresh_scheduler import (
    WatchlistStrategyRefreshScheduler,
    WatchlistStrategyStaleSweep,
)

__all__ = [
    "WatchlistHost",
    "WatchlistPoolHost",
    "WatchlistStrategyRefreshScheduler",
    "WatchlistStrategyStaleSweep",
]
