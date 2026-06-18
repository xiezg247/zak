"""NL 选股工具执行前确认偏好（QSettings）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

NL_SCREENING_CONFIRM_SETTINGS_KEY = "llm/nl_screening_confirm_enabled"


def load_nl_screening_confirm_enabled() -> bool:
    settings = QtCore.QSettings("vnpy_llm", "ZakTerminal")
    value = settings.value(NL_SCREENING_CONFIRM_SETTINGS_KEY)
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "no")
    return bool(value)


def save_nl_screening_confirm_enabled(enabled: bool) -> None:
    settings = QtCore.QSettings("vnpy_llm", "ZakTerminal")
    settings.setValue(NL_SCREENING_CONFIRM_SETTINGS_KEY, bool(enabled))
