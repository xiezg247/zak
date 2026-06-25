"""自选页持仓策略区配置。"""

from __future__ import annotations

from pydantic import Field

from strategies.signals import list_supported_signal_strategies
from vnpy_ashare.config.preferences._settings import coerce_settings_bool, coerce_settings_int, get_settings
from vnpy_ashare.config.preferences._local_ui_pref import load_json_local_ui, save_json_local_ui
from vnpy_ashare.config.preferences._user_pref import load_model_pref, save_model_pref
from vnpy_ashare.config.preferences.watchlist_signal import (
    DEFAULT_CLASS,
    DEFAULT_FAST,
    DEFAULT_SLOW,
    WatchlistSignalConfig,
)
from vnpy_common.domain.base import FrozenModel

POSITION_PANEL_ENABLED_KEY = "watchlist/position_panel/enabled"
POSITION_PANEL_EXPANDED_KEY = "watchlist/position_panel/expanded"
POSITION_FOLLOW_SIGNAL_KEY = "watchlist/position_panel/follow_signal"
POSITION_STRATEGY_KEY = "watchlist/position_panel/strategy"
POSITION_FAST_KEY = "watchlist/position_panel/fast_window"
POSITION_SLOW_KEY = "watchlist/position_panel/slow_window"
POSITION_PANEL_DEFAULT_HEIGHT = 220
POSITION_PANEL_COLLAPSED_HEIGHT = 32

_PREF_NAMESPACE = "watchlist"
_PREF_KEY_CONFIG = "position_config"
_LOCAL_UI_PANEL = "watchlist/position_panel"

_MIGRATE_CONFIG_KEYS = (
    POSITION_FOLLOW_SIGNAL_KEY,
    POSITION_STRATEGY_KEY,
    POSITION_FAST_KEY,
    POSITION_SLOW_KEY,
)


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


def _load_panel_from_qsettings() -> dict[str, bool]:
    settings = get_settings()
    return {
        "enabled": coerce_settings_bool(settings.value(POSITION_PANEL_ENABLED_KEY), default=True),
        "expanded": coerce_settings_bool(settings.value(POSITION_PANEL_EXPANDED_KEY), default=True),
    }


def _load_panel_state() -> dict[str, bool]:
    return load_json_local_ui(
        _LOCAL_UI_PANEL,
        load_default=_load_panel_from_qsettings,
    )


def _save_panel_state(state: dict[str, bool]) -> None:
    save_json_local_ui(_LOCAL_UI_PANEL, state)


def load_position_panel_enabled(*, page_name: str | None = None) -> bool:
    from vnpy_ashare.ui.quotes.page.roles import is_strategy_monitor_page

    state = _load_panel_state()
    if page_name is not None and is_strategy_monitor_page(page_name):
        return bool(state.get("strategy_monitor_enabled", False))
    return bool(state.get("enabled", True))


def save_position_panel_enabled(enabled: bool, *, page_name: str | None = None) -> None:
    from vnpy_ashare.ui.quotes.page.roles import is_strategy_monitor_page

    state = dict(_load_panel_state())
    if page_name is not None and is_strategy_monitor_page(page_name):
        state["strategy_monitor_enabled"] = enabled
    else:
        state["enabled"] = enabled
    _save_panel_state(state)


def load_position_panel_expanded() -> bool:
    return bool(_load_panel_state().get("expanded", True))


def save_position_panel_expanded(expanded: bool) -> None:
    state = dict(_load_panel_state())
    state["expanded"] = expanded
    _save_panel_state(state)


def _load_position_config_from_qsettings() -> WatchlistPositionConfig:
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


def load_watchlist_position_config() -> WatchlistPositionConfig:
    item = load_model_pref(
        _PREF_NAMESPACE,
        _PREF_KEY_CONFIG,
        WatchlistPositionConfig,
        load_legacy=_load_position_config_from_qsettings,
        migrate_keys=_MIGRATE_CONFIG_KEYS,
    )
    return item.normalized()


def save_watchlist_position_config(config: WatchlistPositionConfig) -> None:
    save_model_pref(_PREF_NAMESPACE, _PREF_KEY_CONFIG, config.normalized())
