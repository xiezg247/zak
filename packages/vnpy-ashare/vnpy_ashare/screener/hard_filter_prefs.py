"""选股硬过滤用户偏好（QSettings）；环境变量仍可覆盖。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy.trader.ui import QtCore

from vnpy_ashare.screener.hard_filters import (
    DEFAULT_MIN_AMOUNT_YUAN,
    DEFAULT_MIN_TOTAL_MV_WAN,
)

_SETTINGS = QtCore.QSettings("vnpy_ashare", "ZakTerminal")
_KEY_EXCLUDE_ST = "screener/hard_filter/exclude_st"
_KEY_MIN_AMOUNT_WAN = "screener/hard_filter/min_amount_wan"
_KEY_MIN_TOTAL_MV_YI = "screener/hard_filter/min_total_mv_yi"


@dataclass(frozen=True)
class HardFilterPrefs:
    exclude_st: bool
    min_amount_wan: float
    min_total_mv_yi: float

    @property
    def min_amount_yuan(self) -> float:
        return max(0.0, self.min_amount_wan) * 10_000.0

    @property
    def min_total_mv_wan(self) -> float:
        return max(0.0, self.min_total_mv_yi) * 10_000.0


def default_hard_filter_prefs() -> HardFilterPrefs:
    return HardFilterPrefs(
        exclude_st=True,
        min_amount_wan=DEFAULT_MIN_AMOUNT_YUAN / 10_000.0,
        min_total_mv_yi=DEFAULT_MIN_TOTAL_MV_WAN / 10_000.0,
    )


def load_hard_filter_prefs() -> HardFilterPrefs:
    defaults = default_hard_filter_prefs()
    exclude_st = _SETTINGS.value(_KEY_EXCLUDE_ST)
    if exclude_st is None:
        exclude = defaults.exclude_st
    else:
        exclude = str(exclude_st).strip().lower() not in ("0", "false", "no")

    amount_wan = _read_float(_SETTINGS.value(_KEY_MIN_AMOUNT_WAN), defaults.min_amount_wan)
    mv_yi = _read_float(_SETTINGS.value(_KEY_MIN_TOTAL_MV_YI), defaults.min_total_mv_yi)
    return HardFilterPrefs(
        exclude_st=exclude,
        min_amount_wan=max(0.0, amount_wan),
        min_total_mv_yi=max(0.0, mv_yi),
    )


def save_hard_filter_prefs(prefs: HardFilterPrefs) -> None:
    _SETTINGS.setValue(_KEY_EXCLUDE_ST, prefs.exclude_st)
    _SETTINGS.setValue(_KEY_MIN_AMOUNT_WAN, prefs.min_amount_wan)
    _SETTINGS.setValue(_KEY_MIN_TOTAL_MV_YI, prefs.min_total_mv_yi)


def _read_float(raw, default: float) -> float:
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default
