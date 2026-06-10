"""自选页信号配置与 registry 测试。"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401
from strategies.registry import list_signal_strategy_metas
from vnpy_ashare.ui.quotes.watchlist_signal_settings import (
    DEFAULT_CLASS,
    WatchlistSignalConfig,
)


class WatchlistSignalConfigTests(unittest.TestCase):
    def test_normalized_clamps_windows(self) -> None:
        config = WatchlistSignalConfig(
            class_name=DEFAULT_CLASS,
            fast_window=1,
            slow_window=5,
        ).normalized()
        self.assertEqual(config.fast_window, 2)
        self.assertEqual(config.slow_window, 5)

    def test_normalized_slow_must_exceed_fast(self) -> None:
        config = WatchlistSignalConfig(
            class_name=DEFAULT_CLASS,
            fast_window=20,
            slow_window=15,
        ).normalized()
        self.assertEqual(config.slow_window, 21)

    def test_unknown_strategy_falls_back(self) -> None:
        config = WatchlistSignalConfig(class_name="UnknownStrategy").normalized()
        self.assertEqual(config.class_name, DEFAULT_CLASS)

    def test_cache_key_includes_params(self) -> None:
        a = WatchlistSignalConfig(fast_window=10, slow_window=20).cache_key()
        b = WatchlistSignalConfig(fast_window=12, slow_window=24).cache_key()
        self.assertNotEqual(a, b)
        self.assertIn("AshareDoubleMaStrategy", a)

    def test_to_strategy_setting(self) -> None:
        setting = WatchlistSignalConfig(fast_window=8, slow_window=18).to_strategy_setting()
        self.assertEqual(setting, {"fast_window": 8, "slow_window": 18})


class StrategyRegistrySignalTests(unittest.TestCase):
    def test_double_ma_supports_signals(self) -> None:
        metas = list_signal_strategy_metas()
        self.assertTrue(any(meta.class_name == DEFAULT_CLASS for meta in metas))


if __name__ == "__main__":
    unittest.main()
