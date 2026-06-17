"""策略 Profile 偏好测试。"""

from __future__ import annotations

from vnpy_ashare.config.preferences.strategy_profile import (
    DEFAULT_STRATEGY_PROFILE,
    apply_strategy_profile,
    get_strategy_profile,
    load_strategy_profile_id,
    match_strategy_profile,
    profile_signal_config,
    save_strategy_profile_id,
)
from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig, load_watchlist_signal_config


def test_default_profile_is_medium_watch() -> None:
    assert DEFAULT_STRATEGY_PROFILE == "medium_watch"
    spec = get_strategy_profile(DEFAULT_STRATEGY_PROFILE)
    assert spec.signal_class_name == "AshareDoubleMaStrategy"


def test_apply_strategy_profile_persists_signal_config() -> None:
    cfg = apply_strategy_profile("ultra_short")
    assert cfg.class_name == "AshareLimitBoardStrategy"
    assert cfg.fast_window == 5
    assert load_strategy_profile_id() == "ultra_short"
    loaded = load_watchlist_signal_config()
    assert loaded.class_name == "AshareLimitBoardStrategy"
    save_strategy_profile_id(DEFAULT_STRATEGY_PROFILE)
    apply_strategy_profile(DEFAULT_STRATEGY_PROFILE)


def test_match_strategy_profile() -> None:
    matched = match_strategy_profile(profile_signal_config("trend"))
    assert matched == "trend"
    custom = WatchlistSignalConfig(class_name="AshareDoubleMaStrategy", fast_window=12, slow_window=26)
    assert match_strategy_profile(custom) in {"medium_watch", DEFAULT_STRATEGY_PROFILE}
