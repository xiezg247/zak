"""雷达预测模型模式偏好。"""

from __future__ import annotations

from typing import Literal

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.config.preferences._user_pref import load_scalar_pref, save_scalar_pref

PredictModelMode = Literal["auto", "baseline"]

_SETTINGS_KEY = "quotes/radar/predict_model_mode"
_PREF_NAMESPACE = "radar"
_PREF_KEY = "predict_model_mode"
_DEFAULT_MODE: PredictModelMode = "auto"
_VALID_MODES = frozenset({"auto", "baseline", "lgb"})


def _normalize_mode(raw: str) -> PredictModelMode:
    if raw in _VALID_MODES:
        if raw == "lgb":
            return "baseline"
        return raw  # type: ignore[return-value]
    return _DEFAULT_MODE


def _load_mode_from_qsettings() -> PredictModelMode:
    settings = get_settings()
    raw = str(settings.value(_SETTINGS_KEY, _DEFAULT_MODE) or _DEFAULT_MODE).strip()
    return _normalize_mode(raw)


def load_predict_model_mode() -> PredictModelMode:
    stored = load_scalar_pref(
        _PREF_NAMESPACE,
        _PREF_KEY,
        load_legacy=_load_mode_from_qsettings,
        migrate_key=_SETTINGS_KEY,
    )
    return _normalize_mode(str(stored or _DEFAULT_MODE))


def save_predict_model_mode(mode: PredictModelMode) -> None:
    if mode not in frozenset({"auto", "baseline"}):
        msg = f"未知预测模型模式：{mode}"
        raise ValueError(msg)
    save_scalar_pref(_PREF_NAMESPACE, _PREF_KEY, mode)
