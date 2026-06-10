"""自选页策略信号配置（QSettings 持久化）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from strategies.signals import list_supported_signal_strategies

SETTINGS_ORG = "vnpy_ashare"
SETTINGS_APP = "ZakTerminal"
SIGNAL_STRATEGY_KEY = "watchlist/signal_strategy"
SIGNAL_FAST_KEY = "watchlist/signal_fast_window"
SIGNAL_SLOW_KEY = "watchlist/signal_slow_window"

DEFAULT_CLASS = "AshareDoubleMaStrategy"
DEFAULT_FAST = 10
DEFAULT_SLOW = 20


@dataclass(frozen=True)
class WatchlistSignalConfig:
    class_name: str = DEFAULT_CLASS
    fast_window: int = DEFAULT_FAST
    slow_window: int = DEFAULT_SLOW

    def normalized(self) -> WatchlistSignalConfig:
        supported = set(list_supported_signal_strategies())
        class_name = (self.class_name or DEFAULT_CLASS).strip()
        if class_name not in supported:
            class_name = DEFAULT_CLASS
        fast = max(2, min(int(self.fast_window), 60))
        slow = max(fast + 1, min(int(self.slow_window), 120))
        return WatchlistSignalConfig(class_name=class_name, fast_window=fast, slow_window=slow)

    def cache_key(self) -> str:
        item = self.normalized()
        return f"{item.class_name}:{item.fast_window}:{item.slow_window}"

    def to_strategy_setting(self) -> dict[str, Any]:
        item = self.normalized()
        return {"fast_window": item.fast_window, "slow_window": item.slow_window}


def _settings():
    from vnpy.trader.ui import QtCore

    return QtCore.QSettings(SETTINGS_ORG, SETTINGS_APP)


def load_watchlist_signal_config() -> WatchlistSignalConfig:
    settings = _settings()
    raw_class = settings.value(SIGNAL_STRATEGY_KEY, DEFAULT_CLASS)
    raw_fast = settings.value(SIGNAL_FAST_KEY, DEFAULT_FAST)
    raw_slow = settings.value(SIGNAL_SLOW_KEY, DEFAULT_SLOW)
    try:
        fast = int(raw_fast)
    except (TypeError, ValueError):
        fast = DEFAULT_FAST
    try:
        slow = int(raw_slow)
    except (TypeError, ValueError):
        slow = DEFAULT_SLOW
    return WatchlistSignalConfig(
        class_name=str(raw_class or DEFAULT_CLASS),
        fast_window=fast,
        slow_window=slow,
    ).normalized()


def save_watchlist_signal_config(config: WatchlistSignalConfig) -> None:
    item = config.normalized()
    settings = _settings()
    settings.setValue(SIGNAL_STRATEGY_KEY, item.class_name)
    settings.setValue(SIGNAL_FAST_KEY, item.fast_window)
    settings.setValue(SIGNAL_SLOW_KEY, item.slow_window)
