"""QSettings 共享 org/app 与读写辅助。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

SETTINGS_ORG = "vnpy_ashare"
SETTINGS_APP = "ZakTerminal"


def get_settings() -> QtCore.QSettings:
    return QtCore.QSettings(SETTINGS_ORG, SETTINGS_APP)


def coerce_settings_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
