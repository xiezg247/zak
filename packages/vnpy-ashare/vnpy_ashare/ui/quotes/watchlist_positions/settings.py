"""自选页持仓策略区配置（QSettings 持久化）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

SETTINGS_ORG = "vnpy_ashare"
SETTINGS_APP = "ZakTerminal"
POSITION_PANEL_ENABLED_KEY = "watchlist/position_panel/enabled"
POSITION_PANEL_EXPANDED_KEY = "watchlist/position_panel/expanded"
POSITION_PANEL_DEFAULT_HEIGHT = 220
POSITION_PANEL_COLLAPSED_HEIGHT = 32


def _settings() -> QtCore.QSettings:
    return QtCore.QSettings(SETTINGS_ORG, SETTINGS_APP)


def _coerce_settings_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def load_position_panel_enabled() -> bool:
    settings = _settings()
    return _coerce_settings_bool(settings.value(POSITION_PANEL_ENABLED_KEY), default=True)


def save_position_panel_enabled(enabled: bool) -> None:
    settings = _settings()
    settings.setValue(POSITION_PANEL_ENABLED_KEY, enabled)


def load_position_panel_expanded() -> bool:
    settings = _settings()
    return _coerce_settings_bool(settings.value(POSITION_PANEL_EXPANDED_KEY), default=True)


def save_position_panel_expanded(expanded: bool) -> None:
    settings = _settings()
    settings.setValue(POSITION_PANEL_EXPANDED_KEY, expanded)
