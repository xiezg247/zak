"""策略信号区表格列定义与可见性。

实现已迁至 ``config.preferences.signal_panel_columns``；本模块保留 re-export。
"""

from vnpy_ashare.config.preferences.signal_panel_columns import (
    DEFAULT_VISIBLE_OPTIONAL_KEYS,
    SIGNAL_PANEL_FIXED_KEYS,
    SIGNAL_PANEL_OPTIONAL_COLUMNS,
    SIGNAL_PANEL_OPTIONAL_KEYS,
    normalize_visible_optional_keys,
    resolve_signal_panel_columns,
)

__all__ = [
    "DEFAULT_VISIBLE_OPTIONAL_KEYS",
    "SIGNAL_PANEL_FIXED_KEYS",
    "SIGNAL_PANEL_OPTIONAL_COLUMNS",
    "SIGNAL_PANEL_OPTIONAL_KEYS",
    "normalize_visible_optional_keys",
    "resolve_signal_panel_columns",
]
