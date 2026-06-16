"""雷达预测模型模式偏好（QSettings）。"""

from __future__ import annotations

from typing import Literal

PredictModelMode = Literal["auto", "baseline", "lgb"]

_SETTINGS_KEY = "quotes/radar/predict_model_mode"
_DEFAULT_MODE: PredictModelMode = "auto"
_VALID_MODES = frozenset({"auto", "baseline", "lgb"})


def load_predict_model_mode() -> PredictModelMode:
    from vnpy.trader.ui import QtCore

    settings = QtCore.QSettings("vnpy_ashare", "ZakTerminal")
    raw = str(settings.value(_SETTINGS_KEY, _DEFAULT_MODE) or _DEFAULT_MODE).strip()
    if raw in _VALID_MODES:
        return raw  # type: ignore[return-value]
    return _DEFAULT_MODE


def save_predict_model_mode(mode: PredictModelMode) -> None:
    from vnpy.trader.ui import QtCore

    if mode not in _VALID_MODES:
        msg = f"未知预测模型模式：{mode}"
        raise ValueError(msg)
    settings = QtCore.QSettings("vnpy_ashare", "ZakTerminal")
    settings.setValue(_SETTINGS_KEY, mode)
