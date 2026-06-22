"""自选页策略/持仓工作区开闭偏好。"""

from __future__ import annotations

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.config.preferences.watchlist_position import (
    POSITION_PANEL_EXPANDED_KEY,
    load_position_panel_expanded,
)
from vnpy_ashare.config.preferences.watchlist_signal import (
    SIGNAL_PANEL_EXPANDED_KEY,
    load_signal_panel_expanded,
)

STRATEGY_WORKSPACE_OPEN_KEY = "quotes/watchlist/strategy_workspace_open_v1"


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def load_strategy_workspace_open() -> bool:
    settings = get_settings()
    if settings.contains(STRATEGY_WORKSPACE_OPEN_KEY):
        return _coerce_bool(settings.value(STRATEGY_WORKSPACE_OPEN_KEY, False))
    # 迁移：仅当用户曾持久化过面板展开偏好时保持展开；新用户默认收起
    had_panel_pref = settings.contains(SIGNAL_PANEL_EXPANDED_KEY) or settings.contains(POSITION_PANEL_EXPANDED_KEY)
    if had_panel_pref:
        return load_signal_panel_expanded() or load_position_panel_expanded()
    return False


def save_strategy_workspace_open(open_state: bool) -> None:
    get_settings().setValue(STRATEGY_WORKSPACE_OPEN_KEY, open_state)
