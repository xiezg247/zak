"""雷达主区 Tab 偏好（纯 UI，本机 QSettings，按 user_id 隔离）。"""

from __future__ import annotations

from typing import cast

from vnpy_ashare.config.preferences._local_ui_pref import load_scalar_local_ui, save_scalar_local_ui
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
_LOCAL_UI_MODE = "radar/board_mode"
_LOCAL_UI_RESONANCE_EXPANDED = "radar/resonance_expanded"


def _load_mode_from_legacy() -> RadarCardMode:
    settings = get_settings()
    raw = str(settings.value(_SETTINGS_PREFIX, _DEFAULT_MODE) or _DEFAULT_MODE).strip()
    if raw in _VALID_MODES:
        return cast(RadarCardMode, raw)
    return _DEFAULT_MODE


def load_radar_board_mode() -> RadarCardMode:
    raw = str(
        load_scalar_local_ui(
            _LOCAL_UI_MODE,
            load_default=_load_mode_from_legacy,
        )
        or _DEFAULT_MODE
    ).strip()
    if raw in _VALID_MODES:
        return cast(RadarCardMode, raw)
    return _DEFAULT_MODE


def save_radar_board_mode(mode: RadarCardMode) -> None:
    if mode not in _VALID_MODES:
        return
    save_scalar_local_ui(_LOCAL_UI_MODE, mode)


_RESONANCE_EXPANDED_PREFIX = "quotes/radar/resonance_expanded"


def _load_resonance_expanded_from_legacy(*, default: bool) -> bool:
    settings = get_settings()
    raw = settings.value(_RESONANCE_EXPANDED_PREFIX, default)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def load_radar_resonance_expanded(*, default: bool = True) -> bool:
    value = load_scalar_local_ui(
        _LOCAL_UI_RESONANCE_EXPANDED,
        load_default=lambda: _load_resonance_expanded_from_legacy(default=default),
    )
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def save_radar_resonance_expanded(expanded: bool) -> None:
    save_scalar_local_ui(_LOCAL_UI_RESONANCE_EXPANDED, expanded)


def _group_settings_key(mode: RadarCardMode) -> str:
    return f"quotes/radar/active_group/{mode}"


def _local_ui_group_key(mode: RadarCardMode) -> str:
    return f"radar/active_group/{mode}"


def load_radar_board_group(mode: RadarCardMode) -> RadarGroupKey:
    valid = {key for key, _label in list_radar_groups_for_mode(mode)}
    default = default_group_for_mode(mode)

    def _load_legacy() -> RadarGroupKey:
        settings = get_settings()
        raw = str(settings.value(_group_settings_key(mode), default) or default).strip()
        if raw in valid:
            return cast(RadarGroupKey, raw)
        return default

    raw = str(
        load_scalar_local_ui(
            _local_ui_group_key(mode),
            load_default=_load_legacy,
        )
        or default
    ).strip()
    if raw in valid:
        return cast(RadarGroupKey, raw)
    return default


def save_radar_board_group(mode: RadarCardMode, group_key: RadarGroupKey) -> None:
    valid = {key for key, _label in list_radar_groups_for_mode(mode)}
    if group_key not in valid:
        return
    save_scalar_local_ui(_local_ui_group_key(mode), group_key)
