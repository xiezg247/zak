"""自选页 feature（布局、上下文条、工作流预设）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.features.watchlist.page_feature import WatchlistPageFeature

__all__ = ["WatchlistPageFeature"]


def __getattr__(name: str):
    if name == "WatchlistPageFeature":
        from vnpy_ashare.ui.quotes.features.watchlist.page_feature import WatchlistPageFeature

        return WatchlistPageFeature
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
