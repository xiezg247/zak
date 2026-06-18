"""雷达展望策略偏好测试。"""

from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
from vnpy_ashare.quotes.radar.outlook_strategy_prefs import (
    OUTLOOK_STRATEGY_WHITELIST,
    default_outlook_strategy_class,
    load_outlook_signal_config,
    load_outlook_strategy_class,
    outlook_strategy_label,
    save_outlook_strategy_class,
)


def test_outlook_strategy_whitelist_includes_short_term() -> None:
    assert "AshareShortBreakoutStrategy" in OUTLOOK_STRATEGY_WHITELIST
    assert "AshareLimitBoardStrategy" in OUTLOOK_STRATEGY_WHITELIST
    assert "AshareIntradayBreakoutStrategy" not in OUTLOOK_STRATEGY_WHITELIST


def test_save_and_load_outlook_strategy_class(monkeypatch) -> None:
    store: dict[str, object] = {}

    class _Settings:
        def value(self, key, default=None):
            return store.get(key, default)

        def setValue(self, key, value):
            store[key] = value

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.outlook_strategy_prefs.get_settings",
        lambda: _Settings(),
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.outlook_strategy_prefs.load_watchlist_signal_config",
        lambda: WatchlistSignalConfig(class_name="AshareLimitBoardStrategy", fast_window=5, slow_window=10),
    )

    assert default_outlook_strategy_class() == "AshareLimitBoardStrategy"
    save_outlook_strategy_class("AshareTrendMaStrategy")
    assert load_outlook_strategy_class() == "AshareTrendMaStrategy"
    save_outlook_strategy_class("AshareIntradayBreakoutStrategy")
    assert load_outlook_strategy_class() == "AshareDoubleMaStrategy"


def test_load_outlook_signal_config_uses_strategy_defaults(monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.outlook_strategy_prefs.load_outlook_strategy_class",
        lambda: "AshareTrendMaStrategy",
    )
    config = load_outlook_signal_config()
    assert config.class_name == "AshareTrendMaStrategy"
    assert config.fast_window == 20
    assert config.slow_window == 60
    assert config.cache_key() == "AshareTrendMaStrategy:20:60"


def test_outlook_strategy_label() -> None:
    label = outlook_strategy_label("AshareDoubleMaStrategy")
    assert "双均线" in label
