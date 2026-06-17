"""雷达预测模型模式偏好（QSettings）。"""

from __future__ import annotations

from typing import Literal

from vnpy_ashare.config.preferences._settings import get_settings

PredictModelMode = Literal["auto", "baseline"]

_SETTINGS_KEY = "quotes/radar/predict_model_mode"
_DEFAULT_MODE: PredictModelMode = "auto"
_VALID_MODES = frozenset({"auto", "baseline", "lgb"})


def _normalize_mode(raw: str) -> PredictModelMode:
    if raw in _VALID_MODES:
        if raw == "lgb":
            return "baseline"
        return raw  # type: ignore[return-value]
    return _DEFAULT_MODE


def load_predict_model_mode() -> PredictModelMode:
    settings = get_settings()
    raw = str(settings.value(_SETTINGS_KEY, _DEFAULT_MODE) or _DEFAULT_MODE).strip()
    return _normalize_mode(raw)


def save_predict_model_mode(mode: PredictModelMode) -> None:
    if mode not in frozenset({"auto", "baseline"}):
        msg = f"未知预测模型模式：{mode}"
        raise ValueError(msg)
    settings = get_settings()
    settings.setValue(_SETTINGS_KEY, mode)
