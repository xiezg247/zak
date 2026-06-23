"""自选页信号配置与 registry 测试。"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401
from strategies.registry import list_signal_strategy_metas
from vnpy_ashare.config.preferences.watchlist_signal import (
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
        self.assertIn("AshareShortBreakoutStrategy", a)

    def test_to_strategy_setting(self) -> None:
        setting = WatchlistSignalConfig(fast_window=8, slow_window=18).to_strategy_setting()
        self.assertEqual(setting, {"fast_window": 8, "slow_window": 18})


class StrategyRegistrySignalTests(unittest.TestCase):
    def test_default_strategy_supports_signals(self) -> None:
        metas = list_signal_strategy_metas()
        self.assertTrue(any(meta.class_name == DEFAULT_CLASS for meta in metas))


class SignalPanelSettingsTests(unittest.TestCase):
    def test_panel_symbols_roundtrip(self) -> None:
        save_signal_panel_symbols(["600000.SSE", "000001.SZSE", "600000.SSE"])
        self.assertEqual(load_signal_panel_symbols(), ["600000.SSE", "000001.SZSE"])

    def test_panel_symbols_migrate_tickflow_suffix(self) -> None:
        save_signal_panel_symbols(["600000.SH", "000001.SZ"])
        self.assertEqual(load_signal_panel_symbols(), ["600000.SSE", "000001.SZSE"])

    def test_panel_symbols_respects_max(self) -> None:
        from vnpy_ashare.config.preferences.watchlist_signal import SIGNAL_PANEL_MAX_SYMBOLS, normalize_signal_panel_symbols

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
        from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot, signal_missing_kline

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
        from vnpy_ashare.domain.trading.signal_snapshot import signal_missing_kline

        self.assertFalse(signal_missing_kline(None))


class SignalAsOfStaleTests(unittest.TestCase):
    def test_stale_when_bar_end_differs(self) -> None:
        from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot, signal_as_of_stale

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

    def test_unknown_bar_end_not_stale(self) -> None:
        from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot, signal_as_of_stale

        snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-09",
            signal="buy",
            signal_label="买入",
            signal_date=None,
            ref_buy_price=10.0,
            ref_sell_price=11.0,
            strength=80.0,
            reason_summary="测试",
            reasons=("测试",),
            warnings=(),
        )
        self.assertFalse(signal_as_of_stale(snap, bar_end_date=None))
        self.assertFalse(signal_as_of_stale(snap, bar_end_date=""))

    def test_fresh_when_bar_end_matches(self) -> None:
        from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot, signal_as_of_stale

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
        from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot, signal_as_of_stale

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
        from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot, signal_row_sort_key

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
            "vnpy_ashare.storage.cache.watchlist_signal_cache._cache_db_path",
            return_value=self._db_path,
        )
        self._patcher.start()

    def tearDown(self) -> None:
        self._patcher.stop()
        if self._db_path.exists():
            self._db_path.unlink()
        self._tmp.rmdir()

    def test_disk_cache_roundtrip(self) -> None:
        from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
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
        from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
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

    def test_load_many_accepts_tickflow_symbol(self) -> None:
        from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
        from vnpy_ashare.ui.quotes.watchlist_signals.cache import WatchlistSignalDiskCache

        snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-06",
            signal="buy",
            signal_label="买入",
            signal_date=None,
            ref_buy_price=10.0,
            ref_sell_price=11.0,
            strength=70.0,
            reason_summary="",
            reasons=(),
            warnings=(),
        )
        cache = WatchlistSignalDiskCache()
        config_key = WatchlistSignalConfig().cache_key()
        cache.put(snap, config_key=config_key, bar_as_of="2026-06-06")
        loaded = cache.load_many(
            ["600000.SH"],
            config_key=config_key,
            bar_as_of_for=lambda _vt: "2026-06-06",
        )
        self.assertIn("600000.SH", loaded)
        self.assertEqual(loaded["600000.SH"].signal, "buy")

    def test_load_many_falls_back_to_latest_snapshot(self) -> None:
        from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
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
    def test_normalize_saved_sizes_expanded_signal_not_clipped(self) -> None:
        from unittest.mock import MagicMock

        from vnpy_ashare.ui.quotes.watchlist_signals.splitter import (
            SIGNAL_PANEL_COLLAPSED_HEIGHT,
            SIGNAL_PANEL_DEFAULT_HEIGHT,
            _normalize_saved_sizes,
        )

        signal_panel = MagicMock()
        signal_panel.is_expanded.return_value = True
        signal_panel.minimumHeight.return_value = SIGNAL_PANEL_DEFAULT_HEIGHT

        splitter = MagicMock()
        splitter.count.return_value = 2
        table_host = MagicMock()
        splitter.widget.side_effect = lambda index: table_host if index == 0 else signal_panel
        splitter.height.return_value = 800
        splitter.sizes.return_value = [768, 32]

        page = MagicMock()
        page._market_table_host = table_host
        page.signal_panel = signal_panel
        page.position_panel = None

        with unittest.mock.patch(
            "vnpy_ashare.ui.quotes.watchlist_signals.splitter._run_output_panel",
            return_value=None,
        ):
            normalized = _normalize_saved_sizes(page, splitter, [768, 32])

        self.assertGreaterEqual(normalized[1], SIGNAL_PANEL_DEFAULT_HEIGHT)
        self.assertNotEqual(normalized[1], SIGNAL_PANEL_COLLAPSED_HEIGHT)

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
        from vnpy_ashare.config.preferences.watchlist_signal import load_center_splitter_sizes, save_center_splitter_sizes

        save_center_splitter_sizes([620, 240, 32])
        self.assertEqual(load_center_splitter_sizes(), [620, 240, 32])


class SignalControllerEnabledTests(unittest.TestCase):
    def _make_controller(self, *, enabled: bool) -> tuple[object, object]:
        from unittest.mock import MagicMock

        from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
        from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
        from vnpy_ashare.ui.quotes.watchlist_signals.controller import WatchlistSignalController

        page = MagicMock()
        page.config.show_watchlist_signals = True
        page.page_name = "自选"
        page._active = True
        page.signal_config = WatchlistSignalConfig().normalized()
        page._signal_cache_config = page.signal_config
        page.signal_cache = {
            "600000.SH": SignalSnapshot(
                vt_symbol="600000.SH",
                strategy_id=page.signal_config.class_name,
                as_of="2026-06-20",
                signal="buy",
                signal_label="买入",
                signal_date="2026-06-20",
                ref_buy_price=10.0,
                ref_sell_price=11.0,
                strength=80.0,
                reason_summary="测试",
                reasons=("测试",),
                warnings=(),
            )
        }
        page.continuation_cache = {}
        page.position_cache = {}
        page._get_analysis_service.return_value = MagicMock()
        page._strategy_batch.return_value = MagicMock()

        panel = MagicMock()
        panel.enabled = enabled
        panel.is_expanded.return_value = True
        panel.symbols = ["600000.SH"]
        page.signal_panel = panel

        controller = WatchlistSignalController(page)
        controller._panel_symbols = lambda: ["600000.SH"]
        controller._bar_end_date = lambda _vt: "2026-06-20"
        controller._disk_cache = MagicMock()
        controller._disk_cache.load_many.return_value = {}
        controller._submit_batch = MagicMock()
        controller._apply_refresh_result = MagicMock()
        return controller, page

    def test_manual_refresh_submits_even_when_disabled(self) -> None:
        controller, _page = self._make_controller(enabled=False)
        _page.signal_cache.clear()
        _page._signal_cache_config = None

        controller.refresh(force=True)

        controller._submit_batch.assert_called_once()

    def test_auto_refresh_skips_worker_when_disabled(self) -> None:
        controller, page = self._make_controller(enabled=False)
        page.signal_cache.clear()
        page._signal_cache_config = None

        controller.refresh(force=False)

        controller._submit_batch.assert_not_called()
        controller._apply_refresh_result.assert_called()

    def test_on_panel_enabled_changed_disabled_keeps_display(self) -> None:
        controller, _page = self._make_controller(enabled=False)

        controller.on_panel_enabled_changed(False)

        controller._apply_refresh_result.assert_called_once()
        controller._submit_batch.assert_not_called()

    def test_on_panel_enabled_changed_enabled_refreshes_when_missing(self) -> None:
        controller, page = self._make_controller(enabled=True)
        page.signal_cache.clear()

        controller.on_panel_enabled_changed(True)

        controller._submit_batch.assert_called_once()


class SignalControllerSymbolsChangedTests(unittest.TestCase):
    def test_first_add_triggers_force_refresh(self) -> None:
        from unittest.mock import MagicMock

        from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
        from vnpy_ashare.ui.quotes.watchlist_signals.controller import WatchlistSignalController

        page = MagicMock()
        page.config.show_watchlist_signals = True
        page.page_name = "自选"
        page._active = True
        page.signal_config = WatchlistSignalConfig().normalized()
        page.signal_cache = {}
        page.continuation_cache = {}
        page.watchlist_pool_items.return_value = [MagicMock(vt_symbol="600000.SSE")]

        panel = MagicMock()
        panel.symbols = ["600000.SSE"]
        panel.enabled = True
        page.signal_panel = panel

        controller = WatchlistSignalController(page)
        controller.refresh = MagicMock()
        controller._ensure_bar_meta = MagicMock()
        controller._rekey_signal_cache = MagicMock()
        controller._canonicalize_symbols = lambda symbols: list(symbols)

        controller.on_symbols_changed()

        controller.refresh.assert_called_once_with(symbols=["600000.SSE"], force=True)


class CanonicalVtSymbolTests(unittest.TestCase):
    def test_tickflow_to_vt_symbol(self) -> None:
        from vnpy_ashare.domain.symbols.stock import canonical_vt_symbol

        self.assertEqual(canonical_vt_symbol("600000.SH"), "600000.SSE")
        self.assertEqual(canonical_vt_symbol("000001.SZ"), "000001.SZSE")

    def test_lookup_by_vt_symbol_accepts_tickflow_key(self) -> None:
        from vnpy_ashare.domain.symbols.stock import lookup_by_vt_symbol
        from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot

        snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareShortBreakoutStrategy",
            as_of="2026-06-20",
            signal="buy",
            signal_label="买入",
            signal_date=None,
            ref_buy_price=10.0,
            ref_sell_price=11.0,
            strength=80.0,
            reason_summary="",
            reasons=(),
            warnings=(),
        )
        cache = {"600000.SSE": snap}
        self.assertIs(lookup_by_vt_symbol(cache, "600000.SH"), snap)


class NormalizeSignalPanelSymbolsTests(unittest.TestCase):
    def test_canonicalizes_tickflow_suffix(self) -> None:
        from vnpy_ashare.config.preferences.watchlist_signal import normalize_signal_panel_symbols

        self.assertEqual(
            normalize_signal_panel_symbols(["600000.SH", "000001.SZ"]),
            ["600000.SSE", "000001.SZSE"],
        )


class StrategyBatchRemapTests(unittest.TestCase):
    def test_remap_worker_keys_to_panel_symbols(self) -> None:
        from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
        from vnpy_ashare.ui.quotes.watchlist.strategy_batch import remap_batch_results

        snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareShortBreakoutStrategy",
            as_of="2026-06-20",
            signal="hold",
            signal_label="观望",
            signal_date=None,
            ref_buy_price=None,
            ref_sell_price=None,
            strength=None,
            reason_summary="",
            reasons=(),
            warnings=(),
        )
        mapped = remap_batch_results({"600000.SSE": snap}, ["600000.SH"])
        self.assertIn("600000.SH", mapped)
        self.assertEqual(mapped["600000.SH"].vt_symbol, "600000.SSE")


class SignalControllerCollapsedTests(unittest.TestCase):
    def test_collapsed_still_submits_when_cache_missing(self) -> None:
        from unittest.mock import MagicMock

        from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
        from vnpy_ashare.ui.quotes.watchlist_signals.controller import WatchlistSignalController

        page = MagicMock()
        page.config.show_watchlist_signals = True
        page.page_name = "自选"
        page._active = True
        page.signal_config = WatchlistSignalConfig().normalized()
        page._signal_cache_config = None
        page.signal_cache = {}
        page.continuation_cache = {}
        page._get_analysis_service.return_value = MagicMock()
        page._strategy_batch.return_value = MagicMock()

        panel = MagicMock()
        panel.enabled = True
        panel.is_expanded.return_value = False
        panel.symbols = ["600000.SSE"]
        page.signal_panel = panel

        controller = WatchlistSignalController(page)
        controller._panel_symbols = lambda: ["600000.SSE"]
        controller._bar_end_date = lambda _vt: "2026-06-20"
        controller._disk_cache = MagicMock()
        controller._disk_cache.load_many.return_value = {}
        controller._submit_batch = MagicMock()

        controller.refresh(force=False)

        controller._submit_batch.assert_called_once()


class SignalControllerMemoryCacheTests(unittest.TestCase):
    def test_manual_refresh_keeps_disk_cache(self) -> None:
        from unittest.mock import MagicMock

        from vnpy_ashare.ui.quotes.watchlist_signals.controller import WatchlistSignalController

        page = MagicMock()
        controller = WatchlistSignalController(page)
        controller._disk_cache = MagicMock()

        controller.invalidate_memory_cache()

        controller._disk_cache.clear.assert_not_called()
        page.signal_cache.clear.assert_called_once()


class WorkerPayloadTests(unittest.TestCase):
    def test_unwrap_legacy_dict(self) -> None:
        from vnpy_ashare.ui.quotes.watchlist_signals.worker import unwrap_worker_payload

        payload = unwrap_worker_payload({"600000.SSE": object()})
        self.assertIn("600000.SSE", payload.signals)
        self.assertEqual(payload.continuations, {})

    def test_unwrap_structured_payload(self) -> None:
        from vnpy_ashare.ui.quotes.watchlist_signals.worker import (
            WatchlistSignalWorkerPayload,
            unwrap_worker_payload,
        )

        raw = WatchlistSignalWorkerPayload(signals={"a": 1}, continuations={"a": 2})
        payload = unwrap_worker_payload(raw)
        self.assertEqual(payload.signals, {"a": 1})
        self.assertEqual(payload.continuations, {"a": 2})


class SignalCommitCacheTests(unittest.TestCase):
    def test_commit_maps_tickflow_key_to_panel_symbol(self) -> None:
        from unittest.mock import MagicMock

        from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
        from vnpy_ashare.ui.quotes.watchlist_signals.controller import WatchlistSignalController

        snap = SignalSnapshot(
            vt_symbol="002428.SZSE",
            strategy_id="AshareShortBreakoutStrategy",
            as_of="2026-06-20",
            signal="hold",
            signal_label="观望",
            signal_date=None,
            ref_buy_price=None,
            ref_sell_price=None,
            strength=None,
            reason_summary="",
            reasons=(),
            warnings=(),
        )
        page = MagicMock()
        controller = WatchlistSignalController(page)
        committed = controller._commit_signal_cache(["002428.SZSE"], {"002428.SZ": snap})
        self.assertIn("002428.SZSE", committed)
        self.assertEqual(committed["002428.SZSE"].signal, "hold")


if __name__ == "__main__":
    unittest.main()
