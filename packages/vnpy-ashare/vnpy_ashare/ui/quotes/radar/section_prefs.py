"""雷达主区 Tab 偏好（QSettings）。"""

from __future__ import annotations

from typing import cast

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.quotes.radar.radar_catalog import (
    RADAR_LAYOUT_SECTIONS,
    RadarCardMode,
    RadarGroupKey,
    default_group_for_mode,
    list_radar_groups_for_mode,
)

_SETTINGS_PREFIX = "quotes/radar/active_mode"
_DEFAULT_MODE: RadarCardMode = "statistical"
_VALID_MODES = frozenset(section.mode for section in RADAR_LAYOUT_SECTIONS)


def load_radar_board_mode() -> RadarCardMode:
    settings = get_settings()
    raw = str(settings.value(_SETTINGS_PREFIX, _DEFAULT_MODE) or _DEFAULT_MODE).strip()
    if raw in _VALID_MODES:
        return cast(RadarCardMode, raw)
    return _DEFAULT_MODE


def save_radar_board_mode(mode: RadarCardMode) -> None:
    if mode not in _VALID_MODES:
        return
    settings = get_settings()
    settings.setValue(_SETTINGS_PREFIX, mode)


_RESONANCE_EXPANDED_PREFIX = "quotes/radar/resonance_expanded"


def load_radar_resonance_expanded(*, default: bool = True) -> bool:
    settings = get_settings()
    raw = settings.value(_RESONANCE_EXPANDED_PREFIX, default)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def save_radar_resonance_expanded(expanded: bool) -> None:
    get_settings().setValue(_RESONANCE_EXPANDED_PREFIX, expanded)


def _group_settings_key(mode: RadarCardMode) -> str:
    return f"quotes/radar/active_group/{mode}"


def load_radar_board_group(mode: RadarCardMode) -> RadarGroupKey:
    valid = {key for key, _label in list_radar_groups_for_mode(mode)}
    default = default_group_for_mode(mode)
    settings = get_settings()
    raw = str(settings.value(_group_settings_key(mode), default) or default).strip()
    if raw in valid:
        return cast(RadarGroupKey, raw)
    return default


def save_radar_board_group(mode: RadarCardMode, group_key: RadarGroupKey) -> None:
    valid = {key for key, _label in list_radar_groups_for_mode(mode)}
    if group_key not in valid:
        return
    get_settings().setValue(_group_settings_key(mode), group_key)
