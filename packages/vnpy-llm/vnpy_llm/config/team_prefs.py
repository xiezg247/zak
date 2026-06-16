"""投研团队模式偏好（QSettings + 环境变量兜底）。"""

from __future__ import annotations

import os

from vnpy.trader.ui import QtCore

TEAM_DEEP_MODE_SETTINGS_KEY = "llm/team_deep_mode"


def _team_deep_mode_from_env() -> bool:
    return os.getenv("LLM_TEAM_DEEP_MODE", "").strip().lower() in ("1", "true", "yes")


def load_team_deep_mode_pref() -> bool:
    settings = QtCore.QSettings("vnpy_llm", "ZakTerminal")
    value = settings.value(TEAM_DEEP_MODE_SETTINGS_KEY)
    if value is None:
        return _team_deep_mode_from_env()
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return bool(value)


def save_team_deep_mode_pref(enabled: bool) -> None:
    settings = QtCore.QSettings("vnpy_llm", "ZakTerminal")
    settings.setValue(TEAM_DEEP_MODE_SETTINGS_KEY, bool(enabled))
