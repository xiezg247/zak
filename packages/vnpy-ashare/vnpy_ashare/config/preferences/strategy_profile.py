"""策略 Profile 枚举与偏好持久化（SP-01 / SP-04）。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.config.preferences._user_pref import save_scalar_pref
from vnpy_ashare.config.preferences.watchlist_signal import (
    SIGNAL_STRATEGY_KEY,
    WatchlistSignalConfig,
    load_watchlist_signal_config,
    save_watchlist_signal_config,
)
from vnpy_ashare.screener.hard_filter_prefs import sync_hard_filter_for_strategy_profile
from vnpy_ashare.storage.auth.preferences import batch_get_prefs, get_pref
from vnpy_common.domain.base import FrozenModel

StrategyProfileId = Literal["ultra_short", "short_swing", "medium_watch", "trend"]

STRATEGY_PROFILE_KEY = "trading/strategy_profile"
DEFAULT_STRATEGY_PROFILE: StrategyProfileId = "short_swing"
_PREF_NAMESPACE = "trading"
_PREF_KEY = "strategy_profile"


class StrategyProfileSpec(FrozenModel):
    profile_id: StrategyProfileId = Field(description="策略画像标识")
    title: str = Field(description="策略画像展示标题")
    signal_class_name: str = Field(description="信号策略类名")
    fast_window: int = Field(description="快线窗口")
    slow_window: int = Field(description="慢线窗口")
    transition_hint: str = Field(default="", description="切换提示说明")


STRATEGY_PROFILES: tuple[StrategyProfileSpec, ...] = (
    StrategyProfileSpec(
        profile_id="ultra_short", title="极致短线", signal_class_name="AshareLimitBoardStrategy",
        fast_window=5, slow_window=10, transition_hint="打板日 K 代理；隔日退出绑定 OvernightExit",
    ),
    StrategyProfileSpec(
        profile_id="short_swing", title="短线波段", signal_class_name="AshareShortBreakoutStrategy",
        fast_window=5, slow_window=10, transition_hint="短线放量突破（全局默认）",
    ),
    StrategyProfileSpec(
        profile_id="medium_watch", title="中线观察", signal_class_name="AshareDoubleMaStrategy",
        fast_window=10, slow_window=20,
    ),
    StrategyProfileSpec(
        profile_id="trend", title="趋势中线", signal_class_name="AshareTrendMaStrategy",
        fast_window=20, slow_window=60,
    ),
)

_PROFILE_BY_ID: dict[str, StrategyProfileSpec] = {item.profile_id: item for item in STRATEGY_PROFILES}


def list_strategy_profiles() -> tuple[StrategyProfileSpec, ...]:
    return STRATEGY_PROFILES


def get_strategy_profile(profile_id: str) -> StrategyProfileSpec:
    return _PROFILE_BY_ID.get(profile_id, _PROFILE_BY_ID[DEFAULT_STRATEGY_PROFILE])


def _resolve_profile_id(raw: str | None) -> StrategyProfileId:
    rid = str(raw or DEFAULT_STRATEGY_PROFILE)
    if rid in _PROFILE_BY_ID:
        return rid  # type: ignore[return-value]
    return DEFAULT_STRATEGY_PROFILE


def load_strategy_profile_id() -> StrategyProfileId:
    from vnpy_ashare.config.preferences._user_pref import load_scalar_pref

    stored = load_scalar_pref(
        _PREF_NAMESPACE, _PREF_KEY,
        load_legacy=_load_profile_from_qsettings, migrate_key=STRATEGY_PROFILE_KEY,
    )
    return _resolve_profile_id(str(stored))


def save_strategy_profile_id(profile_id: StrategyProfileId) -> None:
    save_scalar_pref(_PREF_NAMESPACE, _PREF_KEY, profile_id)


def profile_signal_config(profile_id: str) -> WatchlistSignalConfig:
    spec = get_strategy_profile(profile_id)
    return WatchlistSignalConfig(
        class_name=spec.signal_class_name, fast_window=spec.fast_window, slow_window=spec.slow_window,
    ).normalized()


def apply_strategy_profile(profile_id: StrategyProfileId) -> WatchlistSignalConfig:
    cfg = profile_signal_config(profile_id)
    save_strategy_profile_id(profile_id)
    save_watchlist_signal_config(cfg)
    sync_hard_filter_for_strategy_profile(profile_id)
    return cfg


def match_strategy_profile(config: WatchlistSignalConfig | None = None) -> StrategyProfileId:
    item = (config or load_watchlist_signal_config()).normalized()
    for spec in STRATEGY_PROFILES:
        probe = profile_signal_config(spec.profile_id)
        if probe.class_name == item.class_name and probe.fast_window == item.fast_window and probe.slow_window == item.slow_window:
            return spec.profile_id
    return load_strategy_profile_id()


def _load_profile_from_qsettings() -> StrategyProfileId:
    settings = get_settings()
    raw = str(settings.value(STRATEGY_PROFILE_KEY, DEFAULT_STRATEGY_PROFILE) or DEFAULT_STRATEGY_PROFILE)
    return _resolve_profile_id(raw)


def bootstrap_strategy_profile() -> WatchlistSignalConfig:
    """启动时保证 Profile / 信号区 / 硬过滤一致。一次批量查询 + QSettings 合并。"""
    prefs = batch_get_prefs([(_PREF_NAMESPACE, _PREF_KEY), ("watchlist", "signal_config")])

    has_profile = (_PREF_NAMESPACE, _PREF_KEY) in prefs or bool(get_settings().contains(STRATEGY_PROFILE_KEY))
    has_signal = ("watchlist", "signal_config") in prefs or bool(get_settings().contains(SIGNAL_STRATEGY_KEY))

    # 从预拉取值解析 profile_id
    stored_profile = prefs.get((_PREF_NAMESPACE, _PREF_KEY))
    profile_id = _resolve_profile_id(str(stored_profile)) if stored_profile is not None else _load_profile_from_qsettings()

    # 解析信号配置
    stored_signal = prefs.get(("watchlist", "signal_config"))
    if isinstance(stored_signal, dict):
        current = WatchlistSignalConfig.model_validate(stored_signal).normalized()
    else:
        current = load_watchlist_signal_config().normalized()

    if not has_profile and not has_signal:
        return apply_strategy_profile(DEFAULT_STRATEGY_PROFILE)

    if not has_profile:
        matched = match_strategy_profile(current)
        save_strategy_profile_id(matched)
        sync_hard_filter_for_strategy_profile(matched)
        return current

    expected = profile_signal_config(profile_id).normalized()
    if profile_id == DEFAULT_STRATEGY_PROFILE and current.class_name != expected.class_name:
        return apply_strategy_profile(profile_id)

    sync_hard_filter_for_strategy_profile(profile_id)
    return current
