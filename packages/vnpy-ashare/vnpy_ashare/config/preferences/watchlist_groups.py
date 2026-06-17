"""自选分组 QSettings（Service / AI 层可用，不依赖 UI 包）。"""

from __future__ import annotations

from vnpy_ashare.config.preferences._settings import get_settings

_ACTIVE_GROUP_KEY = "watchlist/groups/active_group_id"


def load_active_watchlist_group_id() -> str | None:
    value = str(get_settings().value(_ACTIVE_GROUP_KEY, "") or "").strip()
    return value or None


def save_active_watchlist_group_id(group_id: str | None) -> None:
    get_settings().setValue(_ACTIVE_GROUP_KEY, group_id or "")
