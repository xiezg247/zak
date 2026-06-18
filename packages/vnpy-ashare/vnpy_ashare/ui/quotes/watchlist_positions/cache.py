"""兼容 re-export：实现已迁至 storage.cache.watchlist_position_cache。"""

from vnpy_ashare.storage.cache.watchlist_position_cache import WatchlistPositionDiskCache

__all__ = ["WatchlistPositionDiskCache"]
