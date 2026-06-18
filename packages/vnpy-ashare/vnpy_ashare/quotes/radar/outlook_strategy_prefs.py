"""雷达前瞻展望区策略偏好（与自选信号配置解耦）。"""

from __future__ import annotations

from dataclasses import dataclass

from strategies.registry import OUTLOOK_STRATEGY_CLASS_NAMES, get_strategy_meta
from strategies.signals import STRATEGY_SIGNAL_DEFAULTS, STRATEGY_SIGNAL_RECENT_DAYS
from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.config.preferences.watchlist_signal import (
    DEFAULT_CLASS,
    WatchlistSignalConfig,
    load_watchlist_signal_config,
)

_SETTINGS_KEY = "quotes/radar/outlook_strategy_class"

OUTLOOK_STRATEGY_WHITELIST: tuple[str, ...] = OUTLOOK_STRATEGY_CLASS_NAMES

OUTLOOK_SIGNAL_CARD_IDS: frozenset[str] = frozenset(
    {
        "outlook_watch",
        "outlook_hold",
        "outlook_avoid",
        "outlook_scenario",
    }
)

_WHITELIST_SET = frozenset(OUTLOOK_STRATEGY_WHITELIST)


@dataclass(frozen=True)
class OutlookStrategyOption:
    class_name: str
    label: str


def _normalize_class_name(raw: str) -> str:
    class_name = str(raw or "").strip()
    if class_name in _WHITELIST_SET:
        return class_name
    return DEFAULT_CLASS


def default_outlook_strategy_class() -> str:
    watchlist = load_watchlist_signal_config().normalized()
    if watchlist.class_name in _WHITELIST_SET:
        return watchlist.class_name
    return DEFAULT_CLASS


def load_outlook_strategy_class() -> str:
    settings = get_settings()
    raw = settings.value(_SETTINGS_KEY, "")
    if not raw:
        return default_outlook_strategy_class()
    return _normalize_class_name(str(raw))


def save_outlook_strategy_class(class_name: str) -> None:
    normalized = _normalize_class_name(class_name)
    settings = get_settings()
    settings.setValue(_SETTINGS_KEY, normalized)


def outlook_strategy_options() -> tuple[OutlookStrategyOption, ...]:
    options: list[OutlookStrategyOption] = []
    for class_name in OUTLOOK_STRATEGY_WHITELIST:
        meta = get_strategy_meta(class_name)
        label = meta.title if meta is not None else class_name
        options.append(OutlookStrategyOption(class_name=class_name, label=label))
    return tuple(options)


def outlook_strategy_label(class_name: str) -> str:
    meta = get_strategy_meta(class_name)
    return meta.title if meta is not None else class_name


def load_outlook_signal_config() -> WatchlistSignalConfig:
    class_name = load_outlook_strategy_class()
    fast, slow = STRATEGY_SIGNAL_DEFAULTS.get(class_name, STRATEGY_SIGNAL_DEFAULTS[DEFAULT_CLASS])
    return WatchlistSignalConfig(class_name=class_name, fast_window=fast, slow_window=slow).normalized()


def outlook_signal_recent_days(class_name: str | None = None) -> int:
    resolved = _normalize_class_name(class_name or load_outlook_strategy_class())
    return int(STRATEGY_SIGNAL_RECENT_DAYS.get(resolved, STRATEGY_SIGNAL_RECENT_DAYS[DEFAULT_CLASS]))
