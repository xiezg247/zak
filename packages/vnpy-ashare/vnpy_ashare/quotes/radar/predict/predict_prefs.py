"""雷达预测模型模式偏好（纯 UI，本机 QSettings）。"""

from __future__ import annotations

from typing import Literal

from vnpy_ashare.config.preferences._local_ui_pref import load_scalar_local_ui, save_scalar_local_ui

PredictModelMode = Literal["auto", "baseline"]

_LOCAL_UI_KEY = "radar/predict_model_mode"
_DEFAULT_MODE: PredictModelMode = "auto"
_VALID_MODES = frozenset({"auto", "baseline", "lgb"})


def _normalize_mode(raw: str) -> PredictModelMode:
    if raw in _VALID_MODES:
        if raw == "lgb":
            return "baseline"
        return raw  # type: ignore[return-value]
    return _DEFAULT_MODE


def load_predict_model_mode() -> PredictModelMode:
    stored = load_scalar_local_ui(
        _LOCAL_UI_KEY,
        load_default=lambda: _DEFAULT_MODE,
    )
    return _normalize_mode(str(stored or _DEFAULT_MODE))


def save_predict_model_mode(mode: PredictModelMode) -> None:
    if mode not in frozenset({"auto", "baseline"}):
        msg = f"未知预测模型模式：{mode}"
        raise ValueError(msg)
    save_scalar_local_ui(_LOCAL_UI_KEY, mode)
