"""兼容 import 路径；新代码请使用 watchlist_signals.splitter。"""

from vnpy_ashare.ui.quotes.watchlist_signals.splitter import (
    RUN_OUTPUT_COLLAPSED_HEIGHT,
    RUN_OUTPUT_EXPANDED_HEIGHT,
    SIGNAL_PANEL_COLLAPSED_HEIGHT,
    SIGNAL_PANEL_DEFAULT_HEIGHT,
    apply_center_splitter_sizes,
    center_splitter,
    restore_center_splitter,
)

__all__ = [
    "RUN_OUTPUT_COLLAPSED_HEIGHT",
    "RUN_OUTPUT_EXPANDED_HEIGHT",
    "SIGNAL_PANEL_COLLAPSED_HEIGHT",
    "SIGNAL_PANEL_DEFAULT_HEIGHT",
    "apply_center_splitter_sizes",
    "center_splitter",
    "restore_center_splitter",
]
