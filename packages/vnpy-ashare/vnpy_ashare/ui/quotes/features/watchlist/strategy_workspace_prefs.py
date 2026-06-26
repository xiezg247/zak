"""自选页策略/持仓工作区开闭偏好（纯 UI，本机 QSettings）。"""

from __future__ import annotations

from vnpy_ashare.config.preferences._local_ui_pref import load_scalar_local_ui, save_scalar_local_ui

_LOCAL_UI_KEY = "watchlist/strategy_workspace_open_v1"


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def load_strategy_workspace_open() -> bool:
    value = load_scalar_local_ui(
        _LOCAL_UI_KEY,
        load_default=lambda: False,
    )
    return _coerce_bool(value)


def save_strategy_workspace_open(open_state: bool) -> None:
    save_scalar_local_ui(_LOCAL_UI_KEY, open_state)
