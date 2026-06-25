"""自选页策略信号配置。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from strategies.signals import list_supported_signal_strategies
from vnpy_ashare.config.preferences._local_ui_pref import (
    load_json_local_ui,
    load_scalar_local_ui,
    save_json_local_ui,
    save_scalar_local_ui,
)
from vnpy_ashare.config.preferences._settings import coerce_settings_bool, coerce_settings_int, get_settings
from vnpy_ashare.config.preferences._user_pref import load_model_pref, save_model_pref
from vnpy_ashare.config.preferences.signal_panel_columns import normalize_visible_optional_keys
from vnpy_ashare.domain.symbols.stock import canonical_vt_symbol
from vnpy_common.domain.base import FrozenModel

SIGNAL_STRATEGY_KEY = "watchlist/signal_strategy"
SIGNAL_FAST_KEY = "watchlist/signal_fast_window"
SIGNAL_SLOW_KEY = "watchlist/signal_slow_window"
SIGNAL_PANEL_SYMBOLS_KEY = "watchlist/signal_panel/symbols"
SIGNAL_PANEL_ENABLED_KEY = "watchlist/signal_panel/enabled"
SIGNAL_PANEL_EXPANDED_KEY = "watchlist/signal_panel/expanded"
SIGNAL_PANEL_COLUMNS_KEY = "watchlist/signal_panel/columns"
SIGNAL_STALE_SWEEP_MINUTES_KEY = "watchlist/signal_stale_sweep_minutes"
SIGNAL_CENTER_SPLITTER_SIZES_KEY = "watchlist/center_splitter/sizes"
SIGNAL_PANEL_MAX_SYMBOLS = 10
SIGNAL_LOOKBACK_BARS = 60

DEFAULT_CLASS = "AshareShortBreakoutStrategy"
DEFAULT_FAST = 5
DEFAULT_SLOW = 10
DEFAULT_STALE_SWEEP_MINUTES = 30
MIN_STALE_SWEEP_MINUTES = 5
MAX_STALE_SWEEP_MINUTES = 120

_PREF_NAMESPACE = "watchlist"
_PREF_KEY_CONFIG = "signal_config"
_LOCAL_UI_PANEL = "watchlist/signal_panel"
_LOCAL_UI_SPLITTER = "watchlist/center_splitter_sizes"
_LOCAL_UI_STALE = "watchlist/stale_sweep_minutes"

_MIGRATE_CONFIG_KEYS = (SIGNAL_STRATEGY_KEY, SIGNAL_FAST_KEY, SIGNAL_SLOW_KEY)


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


def _load_signal_config_from_qsettings() -> WatchlistSignalConfig:
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


def load_watchlist_signal_config() -> WatchlistSignalConfig:
    item = load_model_pref(
        _PREF_NAMESPACE,
        _PREF_KEY_CONFIG,
        WatchlistSignalConfig,
        load_legacy=_load_signal_config_from_qsettings,
        migrate_keys=_MIGRATE_CONFIG_KEYS,
    )
    return item.normalized()


def save_watchlist_signal_config(config: WatchlistSignalConfig) -> None:
    save_model_pref(_PREF_NAMESPACE, _PREF_KEY_CONFIG, config.normalized())


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
        raw = str(vt or "").strip()
        text = canonical_vt_symbol(raw) or raw
        if text and text not in seen:
            seen.add(text)
            cleaned.append(text)
            if len(cleaned) >= limit:
                break
    return cleaned


def _load_panel_state_from_qsettings() -> dict[str, object]:
    settings = get_settings()
    raw_symbols = settings.value(SIGNAL_PANEL_SYMBOLS_KEY, "")
    symbols = ""
    if isinstance(raw_symbols, str) and raw_symbols.strip():
        parts = [part.strip() for part in raw_symbols.split(",") if part.strip()]
        symbols = ",".join(normalize_signal_panel_symbols(parts))
    raw_columns = settings.value(SIGNAL_PANEL_COLUMNS_KEY, "")
    columns = ""
    if isinstance(raw_columns, str) and raw_columns.strip():
        parts = [part.strip() for part in raw_columns.split(",") if part.strip()]
        columns = ",".join(normalize_visible_optional_keys(parts))
    return {
        "symbols": symbols,
        "enabled": coerce_settings_bool(settings.value(SIGNAL_PANEL_ENABLED_KEY), default=True),
        "expanded": coerce_settings_bool(settings.value(SIGNAL_PANEL_EXPANDED_KEY), default=True),
        "columns": columns,
    }


def _load_panel_state() -> dict[str, object]:
    return load_json_local_ui(
        _LOCAL_UI_PANEL,
        load_default=_load_panel_state_from_qsettings,
    )


def _save_panel_state(state: dict[str, object]) -> None:
    save_json_local_ui(_LOCAL_UI_PANEL, state)


def load_signal_panel_symbols() -> list[str]:
    raw = str(_load_panel_state().get("symbols") or "")
    if not raw.strip():
        return []
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    return normalize_signal_panel_symbols(parts)


def save_signal_panel_symbols(symbols: list[str]) -> None:
    state = dict(_load_panel_state())
    state["symbols"] = ",".join(normalize_signal_panel_symbols(symbols))
    _save_panel_state(state)


def load_signal_panel_enabled(*, page_name: str | None = None) -> bool:
    from vnpy_ashare.ui.quotes.page.roles import is_strategy_monitor_page

    state = _load_panel_state()
    if page_name is not None and is_strategy_monitor_page(page_name):
        return bool(state.get("strategy_monitor_enabled", False))
    return bool(state.get("enabled", True))


def save_signal_panel_enabled(enabled: bool, *, page_name: str | None = None) -> None:
    from vnpy_ashare.ui.quotes.page.roles import is_strategy_monitor_page

    state = dict(_load_panel_state())
    if page_name is not None and is_strategy_monitor_page(page_name):
        state["strategy_monitor_enabled"] = enabled
    else:
        state["enabled"] = enabled
    _save_panel_state(state)


def load_signal_panel_expanded() -> bool:
    return bool(_load_panel_state().get("expanded", True))


def save_signal_panel_expanded(expanded: bool) -> None:
    state = dict(_load_panel_state())
    state["expanded"] = expanded
    _save_panel_state(state)


def load_signal_panel_columns() -> list[str]:
    raw = str(_load_panel_state().get("columns") or "")
    if not raw.strip():
        return normalize_visible_optional_keys(None)
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    return normalize_visible_optional_keys(parts)


def save_signal_panel_columns(keys: list[str]) -> None:
    state = dict(_load_panel_state())
    state["columns"] = ",".join(normalize_visible_optional_keys(keys))
    _save_panel_state(state)


def _load_splitter_from_qsettings() -> list[int]:
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


def load_center_splitter_sizes() -> list[int]:
    stored = load_json_local_ui(
        _LOCAL_UI_SPLITTER,
        load_default=_load_splitter_from_qsettings,
    )
    if isinstance(stored, list):
        return [max(0, int(value)) for value in stored if isinstance(value, (int, float, str))]
    return _load_splitter_from_qsettings()


def save_center_splitter_sizes(sizes: list[int]) -> None:
    cleaned = [max(0, int(value)) for value in sizes]
    save_json_local_ui(_LOCAL_UI_SPLITTER, cleaned)


def _load_stale_sweep_from_qsettings() -> int:
    settings = get_settings()
    raw = settings.value(SIGNAL_STALE_SWEEP_MINUTES_KEY, DEFAULT_STALE_SWEEP_MINUTES)
    minutes = coerce_settings_int(raw, default=DEFAULT_STALE_SWEEP_MINUTES)
    return max(MIN_STALE_SWEEP_MINUTES, min(minutes, MAX_STALE_SWEEP_MINUTES))


def load_watchlist_strategy_stale_sweep_minutes() -> int:
    value = load_scalar_local_ui(
        _LOCAL_UI_STALE,
        load_default=_load_stale_sweep_from_qsettings,
    )
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        minutes = DEFAULT_STALE_SWEEP_MINUTES
    return max(MIN_STALE_SWEEP_MINUTES, min(minutes, MAX_STALE_SWEEP_MINUTES))


def load_watchlist_strategy_stale_sweep_ms() -> int:
    return load_watchlist_strategy_stale_sweep_minutes() * 60 * 1000


def save_watchlist_strategy_stale_sweep_minutes(minutes: int) -> None:
    value = max(MIN_STALE_SWEEP_MINUTES, min(int(minutes), MAX_STALE_SWEEP_MINUTES))
    save_scalar_local_ui(_LOCAL_UI_STALE, value)
