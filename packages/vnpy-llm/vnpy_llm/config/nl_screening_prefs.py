"""NL 选股工具执行前确认偏好（纯 UI，本机 QSettings）。"""

from __future__ import annotations

from vnpy_ashare.config.preferences._local_ui_pref import load_scalar_local_ui, save_scalar_local_ui

_LOCAL_UI_KEY = "llm/nl_screening_confirm_enabled"


def _coerce_confirm(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "no")
    return bool(value)


def load_nl_screening_confirm_enabled() -> bool:
    value = load_scalar_local_ui(
        _LOCAL_UI_KEY,
        load_default=lambda: True,
    )
    return _coerce_confirm(value)


def save_nl_screening_confirm_enabled(enabled: bool) -> None:
    save_scalar_local_ui(_LOCAL_UI_KEY, bool(enabled))
