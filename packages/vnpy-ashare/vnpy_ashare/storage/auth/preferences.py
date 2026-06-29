"""用户业务偏好（auth.user_preferences）。"""

from __future__ import annotations

from vnpy_ashare.storage.repositories.user_preferences import (
    batch_get_prefs,
    delete_pref,
    delete_prefs,
    get_pref,
    set_pref,
)

_PREFERENCES_TABLE = "auth.user_preferences"


def preferences_table() -> str:
    return _PREFERENCES_TABLE


__all__ = (
    "batch_get_prefs",
    "delete_pref",
    "delete_prefs",
    "get_pref",
    "preferences_table",
    "set_pref",
)
