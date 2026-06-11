"""自选页信号配置与 registry 测试。"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401
from strategies.registry import list_signal_strategy_metas
from vnpy_ashare.ui.quotes.watchlist_signals.settings import (
    DEFAULT_CLASS,
    WatchlistSignalConfig,
    load_signal_panel_enabled,
    load_signal_panel_expanded,
    load_signal_panel_symbols,
    save_signal_panel_enabled,
    save_signal_panel_expanded,
    save_signal_panel_symbols,
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


class SignalPanelSettingsTests(unittest.TestCase):
    def test_panel_symbols_roundtrip(self) -> None:
        save_signal_panel_symbols(["600000.SSE", "000001.SZSE", "600000.SSE"])
        self.assertEqual(load_signal_panel_symbols(), ["600000.SSE", "000001.SZSE"])

    def test_panel_symbols_respects_max(self) -> None:
        from vnpy_ashare.ui.quotes.watchlist_signals.settings import (
            SIGNAL_PANEL_MAX_SYMBOLS,
            normalize_signal_panel_symbols,
        )

        symbols = [f"60000{i}.SSE" for i in range(15)]
        self.assertEqual(len(normalize_signal_panel_symbols(symbols)), SIGNAL_PANEL_MAX_SYMBOLS)
        save_signal_panel_symbols(symbols)
        self.assertEqual(len(load_signal_panel_symbols()), SIGNAL_PANEL_MAX_SYMBOLS)

    def test_panel_defaults(self) -> None:
        save_signal_panel_enabled(True)
        save_signal_panel_expanded(True)
        self.assertTrue(load_signal_panel_enabled())
        self.assertTrue(load_signal_panel_expanded())


class RunOutputSettingsTests(unittest.TestCase):
    def test_run_output_expanded_roundtrip(self) -> None:
        from vnpy_ashare.ui.quotes.page.run_log import load_run_output_expanded, save_run_output_expanded

        save_run_output_expanded("自选", True)
        self.assertTrue(load_run_output_expanded("自选"))
        save_run_output_expanded("自选", False)
        self.assertFalse(load_run_output_expanded("自选"))


class SignalMissingKlineTests(unittest.TestCase):
    def test_detects_kline_warning(self) -> None:
        from vnpy_ashare.domain.signal_snapshot import SignalSnapshot, signal_missing_kline

        snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="",
            signal="na",
            signal_label="—",
            signal_date=None,
            ref_buy_price=None,
            ref_sell_price=None,
            strength=None,
            reason_summary="",
            reasons=(),
            warnings=("本地 K 线不足，请先在数据管理页下载日 K",),
        )
        self.assertTrue(signal_missing_kline(snap))

    def test_ignores_empty_snapshot(self) -> None:
        from vnpy_ashare.domain.signal_snapshot import signal_missing_kline

        self.assertFalse(signal_missing_kline(None))


class SignalAsOfStaleTests(unittest.TestCase):
    def test_stale_when_bar_end_differs(self) -> None:
        from vnpy_ashare.domain.signal_snapshot import SignalSnapshot, signal_as_of_stale

        snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-06",
            signal="hold",
            signal_label="观望",
            signal_date=None,
            ref_buy_price=10.0,
            ref_sell_price=11.0,
            strength=50.0,
            reason_summary="测试",
            reasons=("测试",),
            warnings=(),
        )
        self.assertTrue(signal_as_of_stale(snap, bar_end_date="2026-06-09"))

    def test_fresh_when_bar_end_matches(self) -> None:
        from vnpy_ashare.domain.signal_snapshot import SignalSnapshot, signal_as_of_stale

        snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-09",
            signal="buy",
            signal_label="买入",
            signal_date="2026-06-08",
            ref_buy_price=10.0,
            ref_sell_price=11.0,
            strength=80.0,
            reason_summary="测试",
            reasons=("测试",),
            warnings=(),
        )
        self.assertFalse(signal_as_of_stale(snap, bar_end_date="2026-06-09"))

    def test_missing_kline_not_stale(self) -> None:
        from vnpy_ashare.domain.signal_snapshot import SignalSnapshot, signal_as_of_stale

        snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="",
            signal="na",
            signal_label="—",
            signal_date=None,
            ref_buy_price=None,
            ref_sell_price=None,
            strength=None,
            reason_summary="",
            reasons=(),
            warnings=("本地 K 线不足，请先在数据管理页下载日 K",),
        )
        self.assertFalse(signal_as_of_stale(snap, bar_end_date="2026-06-09"))


class SignalRowSortTests(unittest.TestCase):
    def test_buy_ranks_above_hold(self) -> None:
        from vnpy_ashare.domain.signal_snapshot import SignalSnapshot, signal_row_sort_key

        buy = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-09",
            signal="buy",
            signal_label="买入",
            signal_date=None,
            ref_buy_price=10.0,
            ref_sell_price=11.0,
            strength=60.0,
            reason_summary="",
            reasons=(),
            warnings=(),
        )
        hold = SignalSnapshot(
            vt_symbol="000001.SZSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-09",
            signal="hold",
            signal_label="观望",
            signal_date=None,
            ref_buy_price=None,
            ref_sell_price=None,
            strength=90.0,
            reason_summary="",
            reasons=(),
            warnings=(),
        )
        self.assertGreater(signal_row_sort_key(buy), signal_row_sort_key(hold))


class SignalDiskCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        self._tmp = Path(tempfile.mkdtemp())
        self._db_path = self._tmp / "watchlist_signal_cache.db"
        self._patcher = patch(
            "vnpy_ashare.ui.quotes.watchlist_signals.cache._cache_db_path",
            return_value=self._db_path,
        )
        self._patcher.start()

    def tearDown(self) -> None:
        self._patcher.stop()
        if self._db_path.exists():
            self._db_path.unlink()
        self._tmp.rmdir()

    def test_disk_cache_roundtrip(self) -> None:
        from vnpy_ashare.domain.signal_snapshot import SignalSnapshot
        from vnpy_ashare.ui.quotes.watchlist_signals.cache import WatchlistSignalDiskCache

        snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-09",
            signal="buy",
            signal_label="买入",
            signal_date="2026-06-08",
            ref_buy_price=10.5,
            ref_sell_price=11.2,
            strength=72.0,
            reason_summary="金叉",
            reasons=("MA 金叉",),
            warnings=(),
        )
        cache = WatchlistSignalDiskCache()
        config_key = WatchlistSignalConfig(fast_window=10, slow_window=20).cache_key()
        cache.put(snap, config_key=config_key, bar_as_of="2026-06-09")
        loaded = cache.get("600000.SSE", config_key, "2026-06-09")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.signal, "buy")
        self.assertEqual(loaded.ref_buy_price, 10.5)

    def test_disk_cache_miss_when_bar_as_of_changes(self) -> None:
        from vnpy_ashare.domain.signal_snapshot import SignalSnapshot
        from vnpy_ashare.ui.quotes.watchlist_signals.cache import WatchlistSignalDiskCache

        snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-06",
            signal="hold",
            signal_label="观望",
            signal_date=None,
            ref_buy_price=10.0,
            ref_sell_price=11.0,
            strength=40.0,
            reason_summary="",
            reasons=(),
            warnings=(),
        )
        cache = WatchlistSignalDiskCache()
        config_key = WatchlistSignalConfig().cache_key()
        cache.put(snap, config_key=config_key, bar_as_of="2026-06-06")
        self.assertIsNone(cache.get("600000.SSE", config_key, "2026-06-09"))
        latest = cache.get_latest("600000.SSE", config_key)
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest.signal, "hold")

    def test_load_many_falls_back_to_latest_snapshot(self) -> None:
        from vnpy_ashare.domain.signal_snapshot import SignalSnapshot
        from vnpy_ashare.ui.quotes.watchlist_signals.cache import WatchlistSignalDiskCache

        snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-06",
            signal="sell",
            signal_label="卖出",
            signal_date="2026-06-05",
            ref_buy_price=9.8,
            ref_sell_price=10.1,
            strength=55.0,
            reason_summary="死叉",
            reasons=("MA 死叉",),
            warnings=(),
        )
        cache = WatchlistSignalDiskCache()
        config_key = WatchlistSignalConfig().cache_key()
        cache.put(snap, config_key=config_key, bar_as_of="2026-06-06")
        loaded = cache.load_many(
            ["600000.SSE"],
            config_key=config_key,
            bar_as_of_for=lambda _vt: None,
        )
        self.assertIn("600000.SSE", loaded)
        self.assertEqual(loaded["600000.SSE"].signal, "sell")


class CenterSplitterSizeTests(unittest.TestCase):
    def test_default_signal_height_increased(self) -> None:
        from vnpy_ashare.ui.quotes.watchlist_signals.splitter import (
            SIGNAL_PANEL_DEFAULT_HEIGHT,
            compute_center_splitter_sizes,
        )

        self.assertEqual(SIGNAL_PANEL_DEFAULT_HEIGHT, 240)
        sizes = compute_center_splitter_sizes(
            900,
            has_signal_panel=True,
            signal_expanded=True,
            has_position_panel=False,
            position_expanded=False,
            has_run_output=True,
            run_expanded=False,
        )
        self.assertEqual(sizes["signal"], 240)
        self.assertEqual(sizes["run"], 32)
        self.assertEqual(sizes["table"], 628)

    def test_center_splitter_sizes_roundtrip(self) -> None:
        from vnpy_ashare.ui.quotes.watchlist_signals.settings import (
            load_center_splitter_sizes,
            save_center_splitter_sizes,
        )

        save_center_splitter_sizes([620, 240, 32])
        self.assertEqual(load_center_splitter_sizes(), [620, 240, 32])


if __name__ == "__main__":
    unittest.main()
