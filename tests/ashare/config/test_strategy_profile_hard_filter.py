"""策略 Profile 与硬过滤模板联动测试。"""

from __future__ import annotations

from vnpy_ashare.config.preferences.strategy_profile import (
    DEFAULT_STRATEGY_PROFILE,
    apply_strategy_profile,
)
from vnpy_ashare.screener.hard_filter_prefs import (
    PRESET_AGGRESSIVE,
    PRESET_BALANCED,
    PRESET_CONSERVATIVE,
    hard_filter_preset,
    hard_filter_preset_for_strategy_profile,
    load_hard_filter_prefs,
)


def test_hard_filter_preset_for_strategy_profile_mapping() -> None:
    assert hard_filter_preset_for_strategy_profile("ultra_short") == PRESET_AGGRESSIVE
    assert hard_filter_preset_for_strategy_profile("short_swing") == PRESET_BALANCED
    assert hard_filter_preset_for_strategy_profile("medium_watch") == PRESET_BALANCED
    assert hard_filter_preset_for_strategy_profile("trend") == PRESET_CONSERVATIVE
    assert hard_filter_preset_for_strategy_profile("unknown") == PRESET_BALANCED


def test_apply_strategy_profile_syncs_hard_filter_prefs() -> None:
    apply_strategy_profile("ultra_short")
    ultra = load_hard_filter_prefs()
    assert ultra == hard_filter_preset(PRESET_AGGRESSIVE)

    apply_strategy_profile("trend")
    trend = load_hard_filter_prefs()
    assert trend == hard_filter_preset(PRESET_CONSERVATIVE)

    apply_strategy_profile(DEFAULT_STRATEGY_PROFILE)
    medium = load_hard_filter_prefs()
    assert medium == hard_filter_preset(PRESET_BALANCED)
