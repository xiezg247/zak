"""雷达展望策略偏好测试。"""

from __future__ import annotations

import pytest

from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
from vnpy_ashare.quotes.radar.outlook_strategy_prefs import (
    OUTLOOK_STRATEGY_WHITELIST,
    default_outlook_strategy_class,
    load_outlook_signal_config,
    load_outlook_strategy_class,
    outlook_strategy_label,
    save_outlook_strategy_class,
)


@pytest.fixture
def outlook_pref_store(monkeypatch):
    store: dict[tuple[str, str], object] = {}

    def _load(namespace: str, key: str, *, load_default):
        if (namespace, key) in store:
            return store[(namespace, key)]
        return load_default()

    def _save(namespace: str, key: str, value: object) -> None:
        store[(namespace, key)] = value

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.outlook_strategy_prefs.load_scalar_pref",
        _load,
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.outlook_strategy_prefs.save_scalar_pref",
        _save,
    )
    return store


def test_outlook_strategy_whitelist_includes_short_term() -> None:
    assert "AshareShortBreakoutStrategy" in OUTLOOK_STRATEGY_WHITELIST
    assert "AshareLimitBoardStrategy" in OUTLOOK_STRATEGY_WHITELIST
    assert "AshareIntradayBreakoutStrategy" not in OUTLOOK_STRATEGY_WHITELIST


def test_save_and_load_outlook_strategy_class(monkeypatch, outlook_pref_store) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.outlook_strategy_prefs.load_watchlist_signal_config",
        lambda: WatchlistSignalConfig(class_name="AshareLimitBoardStrategy", fast_window=5, slow_window=10),
    )

    assert default_outlook_strategy_class() == "AshareLimitBoardStrategy"
    save_outlook_strategy_class("AshareTrendMaStrategy")
    assert load_outlook_strategy_class() == "AshareTrendMaStrategy"
    save_outlook_strategy_class("AshareIntradayBreakoutStrategy")
    from vnpy_ashare.config.preferences.watchlist_signal import DEFAULT_CLASS

    assert load_outlook_strategy_class() == DEFAULT_CLASS


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


def test_sector_flow_outlook_fallback_to_radar(monkeypatch, outlook_pref_store) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.outlook_strategy_prefs.load_outlook_strategy_class",
        lambda: "AshareTrendMaStrategy",
    )
    from vnpy_ashare.quotes.radar.outlook_strategy_prefs import load_sector_flow_outlook_strategy_class

    assert load_sector_flow_outlook_strategy_class() == "AshareTrendMaStrategy"


def test_save_and_load_sector_flow_outlook_strategy(outlook_pref_store) -> None:
    from vnpy_ashare.quotes.radar.outlook_strategy_prefs import (
        load_sector_flow_outlook_strategy_class,
        save_sector_flow_outlook_strategy_class,
    )

    save_sector_flow_outlook_strategy_class("AshareDoubleMaStrategy")
    assert load_sector_flow_outlook_strategy_class() == "AshareDoubleMaStrategy"
