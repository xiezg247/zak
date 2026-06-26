"""策略 Profile 偏好与启动 bootstrap 测试。"""

from __future__ import annotations

from tests.ashare.pg_unittest import PgStorageTestCase
from vnpy_ashare.config.preferences.strategy_profile import (
    DEFAULT_STRATEGY_PROFILE,
    apply_strategy_profile,
    bootstrap_strategy_profile,
    get_strategy_profile,
    load_strategy_profile_id,
    match_strategy_profile,
    profile_signal_config,
    save_strategy_profile_id,
)
from vnpy_ashare.config.preferences.watchlist_signal import (
    WatchlistSignalConfig,
    load_watchlist_signal_config,
    save_watchlist_signal_config,
)
from vnpy_ashare.storage.auth.preferences import delete_pref


def test_default_profile_is_short_swing() -> None:
    assert DEFAULT_STRATEGY_PROFILE == "short_swing"
    spec = get_strategy_profile(DEFAULT_STRATEGY_PROFILE)
    assert spec.signal_class_name == "AshareShortBreakoutStrategy"
    assert spec.title == "短线波段"


class StrategyProfilePgTests(PgStorageTestCase):
    def test_apply_strategy_profile_persists_signal_config(self) -> None:
        cfg = apply_strategy_profile("ultra_short")
        assert cfg.class_name == "AshareLimitBoardStrategy"
        assert cfg.fast_window == 5
        assert load_strategy_profile_id() == "ultra_short"
        loaded = load_watchlist_signal_config()
        assert loaded.class_name == "AshareLimitBoardStrategy"
        save_strategy_profile_id(DEFAULT_STRATEGY_PROFILE)
        apply_strategy_profile(DEFAULT_STRATEGY_PROFILE)

    def test_match_strategy_profile(self) -> None:
        matched = match_strategy_profile(profile_signal_config("trend"))
        assert matched == "trend"
        custom = WatchlistSignalConfig(class_name="AshareDoubleMaStrategy", fast_window=12, slow_window=26)
        assert match_strategy_profile(custom) in {"medium_watch", DEFAULT_STRATEGY_PROFILE}

    def test_bootstrap_fresh_install_applies_default(self) -> None:
        delete_pref("trading", "strategy_profile")
        delete_pref("watchlist", "signal_config")
        cfg = bootstrap_strategy_profile()
        assert cfg.class_name == "AshareShortBreakoutStrategy"
        assert load_strategy_profile_id() == "short_swing"
        apply_strategy_profile(DEFAULT_STRATEGY_PROFILE)

    def test_bootstrap_repairs_limit_board_under_default_profile(self) -> None:
        save_strategy_profile_id("short_swing")
        save_watchlist_signal_config(WatchlistSignalConfig(class_name="AshareLimitBoardStrategy", fast_window=5, slow_window=10))
        cfg = bootstrap_strategy_profile()
        assert cfg.class_name == "AshareShortBreakoutStrategy"
        assert load_strategy_profile_id() == "short_swing"
