"""A 股 UI 包。"""

from vnpy_ashare.ui.shell.page_shell import LocalPageWidget, MarketPageWidget, WatchlistPageWidget
from vnpy_ashare.ui.workers import UniverseSyncWorker

__all__ = [
    "LocalPageWidget",
    "MarketPageWidget",
    "UniverseSyncWorker",
    "WatchlistPageWidget",
]
