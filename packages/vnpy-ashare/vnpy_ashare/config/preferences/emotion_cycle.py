"""情绪周期判定阈值。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.config.preferences._settings import (
    coerce_settings_bool,
    coerce_settings_float,
    coerce_settings_int,
    get_settings,
)
from vnpy_ashare.config.preferences._user_pref import load_model_pref, save_model_pref
from vnpy_common.domain.base import FrozenModel

EMOTION_THRESHOLD_PREFIX = "trading/emotion"
_PREF_NAMESPACE = "emotion"
_PREF_KEY = "thresholds"

DEFAULT_RECESSION_LIMIT_DOWN = 20
DEFAULT_ICE_MAX_BOARDS = 2
DEFAULT_ICE_LIMIT_DOWN = 15
DEFAULT_ICE_UP_RATIO_MAX = 0.35
DEFAULT_CLIMAX_LADDER_DEPTH = 3
DEFAULT_CLIMAX_LIMIT_UP = 80
DEFAULT_DIVERGENCE_LIMIT_UP_MIN = 30
DEFAULT_DIVERGENCE_LIMIT_SPREAD = 10
DEFAULT_STARTUP_MAX_BOARDS = 3
DEFAULT_STARTUP_LIMIT_UP = 50
DEFAULT_AMOUNT_FLOOR_YUAN = 1e12
DEFAULT_FEAR_GREED_OVERHEAT = 85.0
DEFAULT_RECESSION_BREAK_RATE = 0.5


class EmotionCycleThresholds(FrozenModel):
    recession_limit_down: int = Field(default=DEFAULT_RECESSION_LIMIT_DOWN, description="退潮：跌停家数下限")
    ice_max_boards: int = Field(default=DEFAULT_ICE_MAX_BOARDS, description="冰点：最高连板上限")
    ice_limit_down: int = Field(default=DEFAULT_ICE_LIMIT_DOWN, description="冰点：跌停家数下限")
    ice_up_ratio_max: float = Field(default=DEFAULT_ICE_UP_RATIO_MAX, description="冰点：上涨占比上限（0–1）")
    climax_ladder_depth: int = Field(default=DEFAULT_CLIMAX_LADDER_DEPTH, description="高潮：连板梯队层数下限")
    climax_limit_up: int = Field(default=DEFAULT_CLIMAX_LIMIT_UP, description="高潮：涨停家数下限")
    divergence_limit_up_min: int = Field(default=DEFAULT_DIVERGENCE_LIMIT_UP_MIN, description="分歧：涨停家数下限")
    divergence_limit_spread: int = Field(default=DEFAULT_DIVERGENCE_LIMIT_SPREAD, description="分歧：涨跌停家数差上限")
    startup_max_boards: int = Field(default=DEFAULT_STARTUP_MAX_BOARDS, description="启动：最高连板下限")
    startup_limit_up: int = Field(default=DEFAULT_STARTUP_LIMIT_UP, description="启动：涨停家数下限")
    amount_floor_yuan: float = Field(default=DEFAULT_AMOUNT_FLOOR_YUAN, description="成交额降仓阈值（元）")
    fear_greed_overheat: float = Field(default=DEFAULT_FEAR_GREED_OVERHEAT, description="恐贪过热提示线")
    recession_break_rate: float = Field(default=DEFAULT_RECESSION_BREAK_RATE, description="退潮：连板断板率下限（0–1）")
    hysteresis_enabled: bool = Field(default=True, description="阶段边界迟滞，减少阈值附近抖动")


DEFAULT_EMOTION_CYCLE_THRESHOLDS = EmotionCycleThresholds()


def _threshold_key(field: str) -> str:
    return f"{EMOTION_THRESHOLD_PREFIX}/{field}"


_MIGRATE_KEYS = tuple(_threshold_key(field) for field in EmotionCycleThresholds.model_fields)


def _load_emotion_from_qsettings() -> EmotionCycleThresholds:
    defaults = DEFAULT_EMOTION_CYCLE_THRESHOLDS
    settings = get_settings()
    return EmotionCycleThresholds(
        recession_limit_down=coerce_settings_int(
            settings.value(_threshold_key("recession_limit_down")),
            default=defaults.recession_limit_down,
        ),
        ice_max_boards=coerce_settings_int(
            settings.value(_threshold_key("ice_max_boards")),
            default=defaults.ice_max_boards,
        ),
        ice_limit_down=coerce_settings_int(
            settings.value(_threshold_key("ice_limit_down")),
            default=defaults.ice_limit_down,
        ),
        ice_up_ratio_max=coerce_settings_float(
            settings.value(_threshold_key("ice_up_ratio_max")),
            default=defaults.ice_up_ratio_max,
        ),
        climax_ladder_depth=coerce_settings_int(
            settings.value(_threshold_key("climax_ladder_depth")),
            default=defaults.climax_ladder_depth,
        ),
        climax_limit_up=coerce_settings_int(
            settings.value(_threshold_key("climax_limit_up")),
            default=defaults.climax_limit_up,
        ),
        divergence_limit_up_min=coerce_settings_int(
            settings.value(_threshold_key("divergence_limit_up_min")),
            default=defaults.divergence_limit_up_min,
        ),
        divergence_limit_spread=coerce_settings_int(
            settings.value(_threshold_key("divergence_limit_spread")),
            default=defaults.divergence_limit_spread,
        ),
        startup_max_boards=coerce_settings_int(
            settings.value(_threshold_key("startup_max_boards")),
            default=defaults.startup_max_boards,
        ),
        startup_limit_up=coerce_settings_int(
            settings.value(_threshold_key("startup_limit_up")),
            default=defaults.startup_limit_up,
        ),
        amount_floor_yuan=coerce_settings_float(
            settings.value(_threshold_key("amount_floor_yuan")),
            default=defaults.amount_floor_yuan,
        ),
        fear_greed_overheat=coerce_settings_float(
            settings.value(_threshold_key("fear_greed_overheat")),
            default=defaults.fear_greed_overheat,
        ),
        recession_break_rate=coerce_settings_float(
            settings.value(_threshold_key("recession_break_rate")),
            default=defaults.recession_break_rate,
        ),
        hysteresis_enabled=coerce_settings_bool(
            settings.value(_threshold_key("hysteresis_enabled")),
            default=defaults.hysteresis_enabled,
        ),
    )


def load_emotion_cycle_thresholds() -> EmotionCycleThresholds:
    return load_model_pref(
        _PREF_NAMESPACE,
        _PREF_KEY,
        EmotionCycleThresholds,
        load_legacy=_load_emotion_from_qsettings,
        migrate_keys=_MIGRATE_KEYS,
    )


def save_emotion_cycle_thresholds(thresholds: EmotionCycleThresholds) -> None:
    save_model_pref(_PREF_NAMESPACE, _PREF_KEY, thresholds)


def reset_emotion_cycle_thresholds() -> EmotionCycleThresholds:
    save_emotion_cycle_thresholds(DEFAULT_EMOTION_CYCLE_THRESHOLDS)
    return DEFAULT_EMOTION_CYCLE_THRESHOLDS


def emotion_thresholds_use_defaults() -> bool:
    return load_emotion_cycle_thresholds() == DEFAULT_EMOTION_CYCLE_THRESHOLDS
