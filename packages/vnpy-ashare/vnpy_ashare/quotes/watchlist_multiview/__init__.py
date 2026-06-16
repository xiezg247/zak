"""自选多维看盘：领域模型与数据加载。"""

from vnpy_ashare.quotes.watchlist_multiview.enrich import enrich_multiview_rows
from vnpy_ashare.quotes.watchlist_multiview.loader import build_watchlist_multiview_board
from vnpy_ashare.quotes.watchlist_multiview.models import (
    WatchlistMultiBoardData,
    WatchlistMultiRow,
    WatchlistMultiSortKey,
)
from vnpy_ashare.quotes.watchlist_multiview.sort import sort_multiview_rows
from vnpy_ashare.quotes.watchlist_multiview.summary import build_multiview_board_summary

__all__ = [
    "WatchlistMultiBoardData",
    "WatchlistMultiRow",
    "WatchlistMultiSortKey",
    "build_multiview_board_summary",
    "build_watchlist_multiview_board",
    "enrich_multiview_rows",
    "sort_multiview_rows",
]
