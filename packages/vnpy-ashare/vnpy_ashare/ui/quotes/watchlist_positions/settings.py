"""自选页持仓策略区配置（QSettings 持久化）。

实现已迁至 ``config.preferences``；本模块保留 re-export 以兼容现有 UI import。
"""

from vnpy_ashare.config.preferences import (
    DEFAULT_CLASS,
    DEFAULT_FAST,
    DEFAULT_SLOW,
    POSITION_PANEL_COLLAPSED_HEIGHT,
    POSITION_PANEL_DEFAULT_HEIGHT,
    WatchlistPositionConfig,
    WatchlistSignalConfig,
    load_position_panel_enabled,
    load_position_panel_expanded,
    load_watchlist_position_config,
    save_position_panel_enabled,
    save_position_panel_expanded,
    save_watchlist_position_config,
)

__all__ = [
    "DEFAULT_CLASS",
    "DEFAULT_FAST",
    "DEFAULT_SLOW",
    "POSITION_PANEL_COLLAPSED_HEIGHT",
    "POSITION_PANEL_DEFAULT_HEIGHT",
    "WatchlistPositionConfig",
    "WatchlistSignalConfig",
    "load_position_panel_enabled",
    "load_position_panel_expanded",
    "load_watchlist_position_config",
    "save_position_panel_enabled",
    "save_position_panel_expanded",
    "save_watchlist_position_config",
]
