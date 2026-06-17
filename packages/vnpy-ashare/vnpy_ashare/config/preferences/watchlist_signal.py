"""自选页策略信号配置（QSettings 持久化）。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from strategies.signals import list_supported_signal_strategies
from vnpy_ashare.config.preferences._settings import coerce_settings_bool, coerce_settings_int, get_settings
from vnpy_ashare.config.preferences.signal_panel_columns import normalize_visible_optional_keys
from vnpy_ashare.domain.base import FrozenModel

SIGNAL_STRATEGY_KEY = "watchlist/signal_strategy"
SIGNAL_FAST_KEY = "watchlist/signal_fast_window"
SIGNAL_SLOW_KEY = "watchlist/signal_slow_window"
SIGNAL_PANEL_SYMBOLS_KEY = "watchlist/signal_panel/symbols"
SIGNAL_PANEL_ENABLED_KEY = "watchlist/signal_panel/enabled"
SIGNAL_PANEL_EXPANDED_KEY = "watchlist/signal_panel/expanded"
SIGNAL_PANEL_COLUMNS_KEY = "watchlist/signal_panel/columns"
SIGNAL_CENTER_SPLITTER_SIZES_KEY = "watchlist/center_splitter/sizes"
SIGNAL_PANEL_MAX_SYMBOLS = 10

DEFAULT_CLASS = "AshareDoubleMaStrategy"
DEFAULT_FAST = 10
DEFAULT_SLOW = 20


class WatchlistSignalConfig(FrozenModel):
    class_name: str = Field(default=DEFAULT_CLASS, description="策略类名")
    fast_window: int = Field(default=DEFAULT_FAST, description="快线窗口")
    slow_window: int = Field(default=DEFAULT_SLOW, description="慢线窗口")

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


def load_watchlist_signal_config() -> WatchlistSignalConfig:
    settings = get_settings()
    raw_class = settings.value(SIGNAL_STRATEGY_KEY, DEFAULT_CLASS)
    raw_fast = settings.value(SIGNAL_FAST_KEY, DEFAULT_FAST)
    raw_slow = settings.value(SIGNAL_SLOW_KEY, DEFAULT_SLOW)
    fast = coerce_settings_int(raw_fast, default=DEFAULT_FAST)
    slow = coerce_settings_int(raw_slow, default=DEFAULT_SLOW)
    return WatchlistSignalConfig(
        class_name=str(raw_class or DEFAULT_CLASS),
        fast_window=fast,
        slow_window=slow,
    ).normalized()


def save_watchlist_signal_config(config: WatchlistSignalConfig) -> None:
    item = config.normalized()
    settings = get_settings()
    settings.setValue(SIGNAL_STRATEGY_KEY, item.class_name)
    settings.setValue(SIGNAL_FAST_KEY, item.fast_window)
    settings.setValue(SIGNAL_SLOW_KEY, item.slow_window)


def normalize_signal_panel_symbols(
    symbols: list[str],
    *,
    max_count: int = SIGNAL_PANEL_MAX_SYMBOLS,
) -> list[str]:
    """去重并截断至信号区上限（保留先出现的顺序）。"""
    cleaned: list[str] = []
    seen: set[str] = set()
    limit = max(1, int(max_count))
    for vt in symbols:
        text = str(vt or "").strip()
        if text and text not in seen:
            seen.add(text)
            cleaned.append(text)
            if len(cleaned) >= limit:
                break
    return cleaned


def load_signal_panel_symbols() -> list[str]:
    settings = get_settings()
    raw = settings.value(SIGNAL_PANEL_SYMBOLS_KEY, "")
    if not isinstance(raw, str) or not raw.strip():
        return []
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    return normalize_signal_panel_symbols(parts)


def save_signal_panel_symbols(symbols: list[str]) -> None:
    settings = get_settings()
    cleaned = normalize_signal_panel_symbols(symbols)
    settings.setValue(SIGNAL_PANEL_SYMBOLS_KEY, ",".join(cleaned))


def load_signal_panel_enabled() -> bool:
    settings = get_settings()
    return coerce_settings_bool(settings.value(SIGNAL_PANEL_ENABLED_KEY), default=True)


def save_signal_panel_enabled(enabled: bool) -> None:
    settings = get_settings()
    settings.setValue(SIGNAL_PANEL_ENABLED_KEY, enabled)


def load_signal_panel_expanded() -> bool:
    settings = get_settings()
    return coerce_settings_bool(settings.value(SIGNAL_PANEL_EXPANDED_KEY), default=True)


def save_signal_panel_expanded(expanded: bool) -> None:
    settings = get_settings()
    settings.setValue(SIGNAL_PANEL_EXPANDED_KEY, expanded)


def load_signal_panel_columns() -> list[str]:
    settings = get_settings()
    raw = settings.value(SIGNAL_PANEL_COLUMNS_KEY, "")
    if not isinstance(raw, str) or not raw.strip():
        return normalize_visible_optional_keys(None)
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    return normalize_visible_optional_keys(parts)


def save_signal_panel_columns(keys: list[str]) -> None:
    settings = get_settings()
    cleaned = normalize_visible_optional_keys(keys)
    settings.setValue(SIGNAL_PANEL_COLUMNS_KEY, ",".join(cleaned))


def load_center_splitter_sizes() -> list[int]:
    settings = get_settings()
    raw = settings.value(SIGNAL_CENTER_SPLITTER_SIZES_KEY)
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        parts = raw
    else:
        text = str(raw).strip()
        if not text:
            return []
        parts = text.split(",")
    sizes: list[int] = []
    for part in parts:
        try:
            sizes.append(max(0, int(part)))
        except (TypeError, ValueError):
            continue
    return sizes


def save_center_splitter_sizes(sizes: list[int]) -> None:
    settings = get_settings()
    cleaned = [max(0, int(value)) for value in sizes]
    settings.setValue(SIGNAL_CENTER_SPLITTER_SIZES_KEY, ",".join(str(value) for value in cleaned))
