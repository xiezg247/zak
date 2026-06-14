"""配方评分 / 动量 / 恐贪调制参数（QSettings）；环境变量仍可覆盖。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy.trader.ui import QtCore

from vnpy_ashare.screener.dimensions.scoring import DEFAULT_METRIC_SCORE_BLEND

_SETTINGS = QtCore.QSettings("vnpy_ashare", "ZakTerminal")
_KEY_PREFIX = "screener/recipe_tuning/"


@dataclass(frozen=True)
class RecipeTuningPrefs:
    metric_score_blend: float
    momentum_min_change_pct: float
    momentum_max_change_pct: float
    momentum_fear_max_change_pct: float
    sentiment_gate_enabled: bool
    extreme_fear_momentum: float
    extreme_fear_sector: float
    extreme_fear_breakout: float
    fear_momentum: float
    extreme_greed_turnover: float
    extreme_greed_volume_surge: float
    greed_turnover: float
    breakout_lookback_days: int
    volume_liquidity_dedup_factor: float


def default_recipe_tuning_prefs() -> RecipeTuningPrefs:
    return RecipeTuningPrefs(
        metric_score_blend=DEFAULT_METRIC_SCORE_BLEND,
        momentum_min_change_pct=0.5,
        momentum_max_change_pct=9.5,
        momentum_fear_max_change_pct=7.0,
        sentiment_gate_enabled=True,
        extreme_fear_momentum=0.08,
        extreme_fear_sector=0.05,
        extreme_fear_breakout=0.04,
        fear_momentum=0.04,
        extreme_greed_turnover=0.05,
        extreme_greed_volume_surge=0.03,
        greed_turnover=0.02,
        breakout_lookback_days=5,
        volume_liquidity_dedup_factor=0.5,
    )


def load_recipe_tuning_prefs() -> RecipeTuningPrefs:
    defaults = default_recipe_tuning_prefs()
    return RecipeTuningPrefs(
        metric_score_blend=_read_float(
            _SETTINGS.value(f"{_KEY_PREFIX}metric_blend"),
            defaults.metric_score_blend,
            0.0,
            1.0,
        ),
        momentum_min_change_pct=_read_float(
            _SETTINGS.value(f"{_KEY_PREFIX}momentum_min"),
            defaults.momentum_min_change_pct,
            0.0,
            20.0,
        ),
        momentum_max_change_pct=_read_float(
            _SETTINGS.value(f"{_KEY_PREFIX}momentum_max"),
            defaults.momentum_max_change_pct,
            0.5,
            30.0,
        ),
        momentum_fear_max_change_pct=_read_float(
            _SETTINGS.value(f"{_KEY_PREFIX}momentum_fear_max"),
            defaults.momentum_fear_max_change_pct,
            0.5,
            30.0,
        ),
        sentiment_gate_enabled=_read_bool(
            _SETTINGS.value(f"{_KEY_PREFIX}sentiment_enabled"),
            defaults.sentiment_gate_enabled,
        ),
        extreme_fear_momentum=_read_float(
            _SETTINGS.value(f"{_KEY_PREFIX}sf_momentum"),
            defaults.extreme_fear_momentum,
            0.0,
            0.5,
        ),
        extreme_fear_sector=_read_float(
            _SETTINGS.value(f"{_KEY_PREFIX}sf_sector"),
            defaults.extreme_fear_sector,
            0.0,
            0.5,
        ),
        extreme_fear_breakout=_read_float(
            _SETTINGS.value(f"{_KEY_PREFIX}sf_breakout"),
            defaults.extreme_fear_breakout,
            0.0,
            0.5,
        ),
        fear_momentum=_read_float(
            _SETTINGS.value(f"{_KEY_PREFIX}fear_momentum"),
            defaults.fear_momentum,
            0.0,
            0.5,
        ),
        extreme_greed_turnover=_read_float(
            _SETTINGS.value(f"{_KEY_PREFIX}sg_turnover"),
            defaults.extreme_greed_turnover,
            0.0,
            0.5,
        ),
        extreme_greed_volume_surge=_read_float(
            _SETTINGS.value(f"{_KEY_PREFIX}sg_volume"),
            defaults.extreme_greed_volume_surge,
            0.0,
            0.5,
        ),
        greed_turnover=_read_float(
            _SETTINGS.value(f"{_KEY_PREFIX}g_turnover"),
            defaults.greed_turnover,
            0.0,
            0.5,
        ),
        breakout_lookback_days=_read_int(
            _SETTINGS.value(f"{_KEY_PREFIX}breakout_lookback"),
            defaults.breakout_lookback_days,
            0,
            60,
        ),
        volume_liquidity_dedup_factor=_read_float(
            _SETTINGS.value(f"{_KEY_PREFIX}volume_dedup"),
            defaults.volume_liquidity_dedup_factor,
            0.0,
            1.0,
        ),
    )


def save_recipe_tuning_prefs(prefs: RecipeTuningPrefs) -> None:
    _SETTINGS.setValue(f"{_KEY_PREFIX}metric_blend", prefs.metric_score_blend)
    _SETTINGS.setValue(f"{_KEY_PREFIX}momentum_min", prefs.momentum_min_change_pct)
    _SETTINGS.setValue(f"{_KEY_PREFIX}momentum_max", prefs.momentum_max_change_pct)
    _SETTINGS.setValue(f"{_KEY_PREFIX}momentum_fear_max", prefs.momentum_fear_max_change_pct)
    _SETTINGS.setValue(f"{_KEY_PREFIX}sentiment_enabled", prefs.sentiment_gate_enabled)
    _SETTINGS.setValue(f"{_KEY_PREFIX}sf_momentum", prefs.extreme_fear_momentum)
    _SETTINGS.setValue(f"{_KEY_PREFIX}sf_sector", prefs.extreme_fear_sector)
    _SETTINGS.setValue(f"{_KEY_PREFIX}sf_breakout", prefs.extreme_fear_breakout)
    _SETTINGS.setValue(f"{_KEY_PREFIX}fear_momentum", prefs.fear_momentum)
    _SETTINGS.setValue(f"{_KEY_PREFIX}sg_turnover", prefs.extreme_greed_turnover)
    _SETTINGS.setValue(f"{_KEY_PREFIX}sg_volume", prefs.extreme_greed_volume_surge)
    _SETTINGS.setValue(f"{_KEY_PREFIX}g_turnover", prefs.greed_turnover)
    _SETTINGS.setValue(f"{_KEY_PREFIX}breakout_lookback", prefs.breakout_lookback_days)
    _SETTINGS.setValue(f"{_KEY_PREFIX}volume_dedup", prefs.volume_liquidity_dedup_factor)


def _read_bool(raw: object, default: bool) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() not in ("0", "false", "no")


def _read_float(raw: object, default: float, min_value: float, max_value: float) -> float:
    if raw is None:
        value = default
    else:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = default
    return max(min_value, min(max_value, value))


def _read_int(raw: object, default: int, min_value: int, max_value: int) -> int:
    if raw is None:
        value = default
    else:
        try:
            value = int(float(raw))
        except (TypeError, ValueError):
            value = default
    return max(min_value, min(max_value, value))
