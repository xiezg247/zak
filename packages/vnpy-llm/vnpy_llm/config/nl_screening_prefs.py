"""NL 选股工具执行前确认偏好（纯 UI，本机 QSettings）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.config.preferences._local_ui_pref import load_scalar_local_ui, save_scalar_local_ui

NL_SCREENING_CONFIRM_SETTINGS_KEY = "llm/nl_screening_confirm_enabled"
_LOCAL_UI_KEY = "llm/nl_screening_confirm_enabled"


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


def _load_confirm_from_legacy() -> bool:
    return _coerce_confirm(_llm_settings().value(NL_SCREENING_CONFIRM_SETTINGS_KEY))


def load_nl_screening_confirm_enabled() -> bool:
    value = load_scalar_local_ui(
        _LOCAL_UI_KEY,
        load_default=_load_confirm_from_legacy,
    )
    return _coerce_confirm(value)


def save_nl_screening_confirm_enabled(enabled: bool) -> None:
    save_scalar_local_ui(_LOCAL_UI_KEY, bool(enabled))
