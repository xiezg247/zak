"""自选分组活跃组偏好。"""

from __future__ import annotations

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.config.preferences._user_pref import load_scalar_pref, save_scalar_pref

_ACTIVE_GROUP_KEY = "watchlist/groups/active_group_id"
_PREF_NAMESPACE = "watchlist"
_PREF_KEY = "active_group_id"


def _load_active_from_qsettings() -> str | None:
    value = str(get_settings().value(_ACTIVE_GROUP_KEY, "") or "").strip()
    return value or None


def load_active_watchlist_group_id() -> str | None:
    value = load_scalar_pref(
        _PREF_NAMESPACE,
        _PREF_KEY,
        load_legacy=_load_active_from_qsettings,
        migrate_key=_ACTIVE_GROUP_KEY,
    )
    text = str(value or "").strip()
    return text or None


def save_active_watchlist_group_id(group_id: str | None) -> None:
    save_scalar_pref(_PREF_NAMESPACE, _PREF_KEY, group_id or "")
