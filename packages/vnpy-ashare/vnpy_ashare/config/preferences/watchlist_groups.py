"""自选分组活跃组偏好。"""

from __future__ import annotations

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.config.preferences._local_ui_pref import load_scalar_local_ui, save_scalar_local_ui

_ACTIVE_GROUP_KEY = "watchlist/groups/active_group_id"
_LOCAL_UI_ACTIVE_GROUP = "watchlist/active_group_id"


def _load_active_from_qsettings() -> str | None:
    value = str(get_settings().value(_ACTIVE_GROUP_KEY, "") or "").strip()
    return value or None


def load_active_watchlist_group_id() -> str | None:
    value = load_scalar_local_ui(
        _LOCAL_UI_ACTIVE_GROUP,
        load_default=_load_active_from_qsettings,
    )
    text = str(value or "").strip()
    return text or None


def save_active_watchlist_group_id(group_id: str | None) -> None:
    save_scalar_local_ui(_LOCAL_UI_ACTIVE_GROUP, group_id or "")
