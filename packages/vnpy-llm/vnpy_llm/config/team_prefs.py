"""投研团队模式偏好（user_preferences + 环境变量兜底）。"""

from __future__ import annotations

import os

from vnpy.trader.ui import QtCore

from vnpy_ashare.config.preferences._user_pref import save_scalar_pref
from vnpy_ashare.storage.auth.preferences import get_pref

TEAM_DEEP_MODE_SETTINGS_KEY = "llm/team_deep_mode"
_PREF_NAMESPACE = "llm"
_PREF_KEY = "team_deep_mode"


def _team_deep_mode_from_env() -> bool:
    return os.getenv("LLM_TEAM_DEEP_MODE", "").strip().lower() in ("1", "true", "yes")


def _llm_settings() -> QtCore.QSettings:
    return QtCore.QSettings("vnpy_llm", "ZakTerminal")


def _coerce_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return bool(value)


def load_team_deep_mode_pref() -> bool:
    stored = get_pref(_PREF_NAMESPACE, _PREF_KEY, None)
    if stored is not None:
        return _coerce_bool(stored, default=_team_deep_mode_from_env())
    legacy = _coerce_bool(_llm_settings().value(TEAM_DEEP_MODE_SETTINGS_KEY), default=_team_deep_mode_from_env())
    if _llm_settings().value(TEAM_DEEP_MODE_SETTINGS_KEY) is not None:
        save_scalar_pref(_PREF_NAMESPACE, _PREF_KEY, legacy)
    return legacy


def save_team_deep_mode_pref(enabled: bool) -> None:
    save_scalar_pref(_PREF_NAMESPACE, _PREF_KEY, bool(enabled))
