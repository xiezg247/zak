"""QSettings 共享 org/app 与读写辅助。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtCore

from vnpy_common.paths import QSETTINGS_ORG, SETTINGS_APP


def get_settings() -> QtCore.QSettings:
    return QtCore.QSettings(QSETTINGS_ORG, SETTINGS_APP)


def _legacy_settings(org: str, app: str) -> QtCore.QSettings:
    return QtCore.QSettings(org, app)


def read_migrated_value(
    new_key: str,
    legacy_profiles: tuple[tuple[str, str, str], ...],
    default: Any = None,
) -> Any:
    """读取设置：当前 profile 优先，再按 legacy (org, app, key) 回退。"""
    val = get_settings().value(new_key)
    if val is not None:
        return val
    for org, app, legacy_key in legacy_profiles:
        legacy_val = _legacy_settings(org, app).value(legacy_key)
        if legacy_val is not None:
            return legacy_val
    return default


def write_setting_value(key: str, value: Any) -> None:
    get_settings().setValue(key, value)


def coerce_settings_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def coerce_settings_int(value: object, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    if isinstance(value, float):
        return int(value)
    return default


def coerce_settings_float(value: object, *, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default
