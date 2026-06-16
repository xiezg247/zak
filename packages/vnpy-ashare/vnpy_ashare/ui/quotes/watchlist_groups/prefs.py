"""自选分组 QSettings。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

_ACTIVE_GROUP_KEY = "watchlist/groups/active_group_id"


def load_active_watchlist_group_id() -> str | None:
    settings = QtCore.QSettings("vnpy_ashare", "ZakTerminal")
    value = str(settings.value(_ACTIVE_GROUP_KEY, "") or "").strip()
    return value or None


def save_active_watchlist_group_id(group_id: str | None) -> None:
    settings = QtCore.QSettings("vnpy_ashare", "ZakTerminal")
    settings.setValue(_ACTIVE_GROUP_KEY, group_id or "")
