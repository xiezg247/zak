"""自选页持仓策略区配置（QSettings 持久化）。"""

from __future__ import annotations

from pydantic import Field

from strategies.signals import list_supported_signal_strategies
from vnpy_ashare.config.preferences._settings import coerce_settings_bool, coerce_settings_int, get_settings
from vnpy_ashare.config.preferences.watchlist_signal import (
    DEFAULT_CLASS,
    DEFAULT_FAST,
    DEFAULT_SLOW,
    WatchlistSignalConfig,
)
from vnpy_ashare.domain.base import FrozenModel

POSITION_PANEL_ENABLED_KEY = "watchlist/position_panel/enabled"
POSITION_PANEL_EXPANDED_KEY = "watchlist/position_panel/expanded"
POSITION_FOLLOW_SIGNAL_KEY = "watchlist/position_panel/follow_signal"
POSITION_STRATEGY_KEY = "watchlist/position_panel/strategy"
POSITION_FAST_KEY = "watchlist/position_panel/fast_window"
POSITION_SLOW_KEY = "watchlist/position_panel/slow_window"
POSITION_PANEL_DEFAULT_HEIGHT = 220
POSITION_PANEL_COLLAPSED_HEIGHT = 32


class WatchlistPositionConfig(FrozenModel):
    follow_signal: bool = Field(default=True, description="是否跟随信号区策略")
    class_name: str = Field(default=DEFAULT_CLASS, description="策略类名")
    fast_window: int = Field(default=DEFAULT_FAST, description="快线窗口")
    slow_window: int = Field(default=DEFAULT_SLOW, description="慢线窗口")

    def normalized(self) -> WatchlistPositionConfig:
        supported = set(list_supported_signal_strategies())
        class_name = (self.class_name or DEFAULT_CLASS).strip()
        if class_name not in supported:
            class_name = DEFAULT_CLASS
        fast = max(2, min(int(self.fast_window), 60))
        slow = max(fast + 1, min(int(self.slow_window), 120))
        return WatchlistPositionConfig(
            follow_signal=bool(self.follow_signal),
            class_name=class_name,
            fast_window=fast,
            slow_window=slow,
        )

    def effective_signal_config(self, signal_config: WatchlistSignalConfig) -> WatchlistSignalConfig:
        if self.follow_signal:
            return signal_config.normalized()
        item = self.normalized()
        return WatchlistSignalConfig(
            class_name=item.class_name,
            fast_window=item.fast_window,
            slow_window=item.slow_window,
        ).normalized()


def load_position_panel_enabled() -> bool:
    settings = get_settings()
    return coerce_settings_bool(settings.value(POSITION_PANEL_ENABLED_KEY), default=True)


def save_position_panel_enabled(enabled: bool) -> None:
    settings = get_settings()
    settings.setValue(POSITION_PANEL_ENABLED_KEY, enabled)


def load_position_panel_expanded() -> bool:
    settings = get_settings()
    return coerce_settings_bool(settings.value(POSITION_PANEL_EXPANDED_KEY), default=True)


def save_position_panel_expanded(expanded: bool) -> None:
    settings = get_settings()
    settings.setValue(POSITION_PANEL_EXPANDED_KEY, expanded)


def load_watchlist_position_config() -> WatchlistPositionConfig:
    settings = get_settings()
    follow = coerce_settings_bool(settings.value(POSITION_FOLLOW_SIGNAL_KEY), default=True)
    raw_class = settings.value(POSITION_STRATEGY_KEY, DEFAULT_CLASS)
    raw_fast = settings.value(POSITION_FAST_KEY, DEFAULT_FAST)
    raw_slow = settings.value(POSITION_SLOW_KEY, DEFAULT_SLOW)
    fast = coerce_settings_int(raw_fast, default=DEFAULT_FAST)
    slow = coerce_settings_int(raw_slow, default=DEFAULT_SLOW)
    return WatchlistPositionConfig(
        follow_signal=follow,
        class_name=str(raw_class or DEFAULT_CLASS),
        fast_window=fast,
        slow_window=slow,
    ).normalized()


def save_watchlist_position_config(config: WatchlistPositionConfig) -> None:
    item = config.normalized()
    settings = get_settings()
    settings.setValue(POSITION_FOLLOW_SIGNAL_KEY, item.follow_signal)
    settings.setValue(POSITION_STRATEGY_KEY, item.class_name)
    settings.setValue(POSITION_FAST_KEY, item.fast_window)
    settings.setValue(POSITION_SLOW_KEY, item.slow_window)
