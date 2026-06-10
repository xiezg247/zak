"""A 股 UI 包 barrel（页面 Widget 与兼容 Worker re-export）。"""

from .page_shell import LocalPageWidget, MarketPageWidget, WatchlistPageWidget
from .worker import UniverseSyncWorker

__all__ = [
    "LocalPageWidget",
    "MarketPageWidget",
    "UniverseSyncWorker",
    "WatchlistPageWidget",
]
