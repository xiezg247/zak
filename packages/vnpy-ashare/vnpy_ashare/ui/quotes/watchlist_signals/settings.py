"""自选页策略信号配置（QSettings 持久化）。

实现已迁至 ``config.preferences``；本模块保留 re-export 以兼容现有 UI import。
"""

from vnpy_ashare.config.preferences import (
    DEFAULT_CLASS,
    DEFAULT_FAST,
    DEFAULT_SLOW,
    SETTINGS_APP,
    SETTINGS_ORG,
    SIGNAL_PANEL_MAX_SYMBOLS,
    WatchlistSignalConfig,
    load_center_splitter_sizes,
    load_signal_panel_columns,
    load_signal_panel_enabled,
    load_signal_panel_expanded,
    load_signal_panel_symbols,
    load_watchlist_signal_config,
    normalize_signal_panel_symbols,
    save_center_splitter_sizes,
    save_signal_panel_columns,
    save_signal_panel_enabled,
    save_signal_panel_expanded,
    save_signal_panel_symbols,
    save_watchlist_signal_config,
)

__all__ = [
    "DEFAULT_CLASS",
    "DEFAULT_FAST",
    "DEFAULT_SLOW",
    "SETTINGS_APP",
    "SETTINGS_ORG",
    "SIGNAL_PANEL_MAX_SYMBOLS",
    "WatchlistSignalConfig",
    "load_center_splitter_sizes",
    "load_signal_panel_columns",
    "load_signal_panel_enabled",
    "load_signal_panel_expanded",
    "load_signal_panel_symbols",
    "load_watchlist_signal_config",
    "normalize_signal_panel_symbols",
    "save_center_splitter_sizes",
    "save_signal_panel_columns",
    "save_signal_panel_enabled",
    "save_signal_panel_expanded",
    "save_signal_panel_symbols",
    "save_watchlist_signal_config",
]
