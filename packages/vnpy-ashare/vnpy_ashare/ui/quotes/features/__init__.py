"""看盘页 feature 模块（按 Tab / 侧栏拆分）。"""

from vnpy_ashare.ui.quotes.features.market_rank import RANK_SETTINGS_KEY, MarketRankFeature
from vnpy_ashare.ui.quotes.features.stock_notes import StockNotesFeature
from vnpy_ashare.ui.quotes.features.watchlist_panels import WatchlistPanelsFeature

__all__ = [
    "MarketRankFeature",
    "RANK_SETTINGS_KEY",
    "StockNotesFeature",
    "WatchlistPanelsFeature",
]
