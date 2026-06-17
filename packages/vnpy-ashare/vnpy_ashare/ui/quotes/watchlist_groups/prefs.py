"""自选分组 QSettings。"""

from __future__ import annotations

from vnpy_ashare.config.preferences.watchlist_groups import (
    load_active_watchlist_group_id,
    save_active_watchlist_group_id,
)

__all__ = ["load_active_watchlist_group_id", "save_active_watchlist_group_id"]
