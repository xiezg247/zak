"""A 股 UI 包。"""

from vnpy_ashare.ui.quotes.workers import UniverseSyncWorker
from vnpy_ashare.ui.shell.page_shell import LocalPageWidget, MarketPageWidget, WatchlistPageWidget

__all__ = [
    "LocalPageWidget",
    "MarketPageWidget",
    "UniverseSyncWorker",
    "WatchlistPageWidget",
]
