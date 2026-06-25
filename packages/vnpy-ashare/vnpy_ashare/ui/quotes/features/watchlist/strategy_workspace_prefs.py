"""自选页策略/持仓工作区开闭偏好（纯 UI，本机 QSettings）。"""

from __future__ import annotations

from vnpy_ashare.config.preferences._local_ui_pref import load_scalar_local_ui, save_scalar_local_ui
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
_LOCAL_UI_KEY = "watchlist/strategy_workspace_open_v1"


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _load_open_from_legacy() -> bool:
    settings = get_settings()
    if settings.contains(STRATEGY_WORKSPACE_OPEN_KEY):
        return _coerce_bool(settings.value(STRATEGY_WORKSPACE_OPEN_KEY, False))
    had_panel_pref = settings.contains(SIGNAL_PANEL_EXPANDED_KEY) or settings.contains(POSITION_PANEL_EXPANDED_KEY)
    if had_panel_pref:
        return load_signal_panel_expanded() or load_position_panel_expanded()
    return False


def load_strategy_workspace_open() -> bool:
    value = load_scalar_local_ui(
        _LOCAL_UI_KEY,
        load_default=_load_open_from_legacy,
    )
    return _coerce_bool(value)


def save_strategy_workspace_open(open_state: bool) -> None:
    save_scalar_local_ui(_LOCAL_UI_KEY, open_state)
