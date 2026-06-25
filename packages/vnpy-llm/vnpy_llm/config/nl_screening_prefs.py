"""NL 选股工具执行前确认偏好。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.config.preferences._user_pref import save_scalar_pref
from vnpy_ashare.storage.auth.preferences import get_pref

NL_SCREENING_CONFIRM_SETTINGS_KEY = "llm/nl_screening_confirm_enabled"
_PREF_NAMESPACE = "llm"
_PREF_KEY = "nl_screening_confirm_enabled"


def _llm_settings() -> QtCore.QSettings:
    return QtCore.QSettings("vnpy_llm", "ZakTerminal")


def _coerce_confirm(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "no")
    return bool(value)


def load_nl_screening_confirm_enabled() -> bool:
    stored = get_pref(_PREF_NAMESPACE, _PREF_KEY, None)
    if stored is not None:
        return _coerce_confirm(stored)
    legacy = _coerce_confirm(_llm_settings().value(NL_SCREENING_CONFIRM_SETTINGS_KEY))
    if _llm_settings().value(NL_SCREENING_CONFIRM_SETTINGS_KEY) is not None:
        save_scalar_pref(_PREF_NAMESPACE, _PREF_KEY, legacy)
    return legacy


def save_nl_screening_confirm_enabled(enabled: bool) -> None:
    save_scalar_pref(_PREF_NAMESPACE, _PREF_KEY, bool(enabled))
