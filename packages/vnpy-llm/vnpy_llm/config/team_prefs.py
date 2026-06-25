"""投研团队模式偏好（user_preferences + 环境变量兜底）。"""

from __future__ import annotations

import os

from vnpy_ashare.config.preferences._settings import coerce_settings_bool, read_migrated_value
from vnpy_ashare.config.preferences._user_pref import save_scalar_pref
from vnpy_ashare.storage.auth.preferences import get_pref
from vnpy_common.paths import SETTINGS_APP

TEAM_DEEP_MODE_SETTINGS_KEY = "llm/team_deep_mode"
_PREF_NAMESPACE = "llm"
_PREF_KEY = "team_deep_mode"
_LEGACY_TEAM_DEEP = (("vnpy_llm", SETTINGS_APP, TEAM_DEEP_MODE_SETTINGS_KEY),)


def _team_deep_mode_from_env() -> bool:
    return os.getenv("LLM_TEAM_DEEP_MODE", "").strip().lower() in ("1", "true", "yes")


def load_team_deep_mode_pref() -> bool:
    stored = get_pref(_PREF_NAMESPACE, _PREF_KEY, None)
    if stored is not None:
        return coerce_settings_bool(stored, default=_team_deep_mode_from_env())
    legacy_raw = read_migrated_value(TEAM_DEEP_MODE_SETTINGS_KEY, _LEGACY_TEAM_DEEP, None)
    legacy = coerce_settings_bool(legacy_raw, default=_team_deep_mode_from_env())
    if legacy_raw is not None:
        save_scalar_pref(_PREF_NAMESPACE, _PREF_KEY, legacy)
    return legacy


def save_team_deep_mode_pref(enabled: bool) -> None:
    save_scalar_pref(_PREF_NAMESPACE, _PREF_KEY, bool(enabled))
