"""兼容 re-export：实现已迁至 storage.cache.watchlist_signal_cache。"""

from vnpy_ashare.storage.cache.watchlist_signal_cache import (
    WatchlistSignalDiskCache,
    snapshot_from_payload,
    snapshot_to_payload,
)

__all__ = [
    "WatchlistSignalDiskCache",
    "snapshot_from_payload",
    "snapshot_to_payload",
]
