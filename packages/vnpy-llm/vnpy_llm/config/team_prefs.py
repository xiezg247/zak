"""投研团队模式偏好（纯 UI，本机 QSettings；环境变量仍可兜底）。"""

from __future__ import annotations

import os

from vnpy_ashare.config.preferences._local_ui_pref import load_scalar_local_ui, save_scalar_local_ui

_LOCAL_UI_KEY = "llm/team_deep_mode"


def _team_deep_mode_from_env() -> bool:
    return os.getenv("LLM_TEAM_DEEP_MODE", "").strip().lower() in ("1", "true", "yes")


def load_team_deep_mode_pref() -> bool:
    return bool(
        load_scalar_local_ui(
            _LOCAL_UI_KEY,
            load_default=_team_deep_mode_from_env,
        )
    )


def save_team_deep_mode_pref(enabled: bool) -> None:
    save_scalar_local_ui(_LOCAL_UI_KEY, bool(enabled))
