"""自选页持仓区设置与磁盘缓存测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.config.preferences.watchlist_position import (
    WatchlistPositionConfig,
    load_position_panel_enabled,
    load_position_panel_expanded,
    load_watchlist_position_config,
    save_position_panel_enabled,
    save_position_panel_expanded,
    save_watchlist_position_config,
)
from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.ui.quotes.watchlist_positions.cache import WatchlistPositionDiskCache


def _sample_signal(vt_symbol: str = "600000.SSE") -> SignalSnapshot:
    return SignalSnapshot(
        vt_symbol=vt_symbol,
        strategy_id="AshareDoubleMaStrategy",
        as_of="2026-06-10",
        signal="sell",
        signal_label="卖出",
        signal_date="2026-06-09",
        ref_buy_price=10.0,
        ref_sell_price=9.5,
        strength=70.0,
        reason_summary="死叉",
        reasons=("MA 死叉",),
        warnings=(),
    )


class PositionPanelSettingsTests(unittest.TestCase):
    def test_panel_defaults_roundtrip(self) -> None:
        save_position_panel_enabled(True)
        save_position_panel_expanded(True)
        self.assertTrue(load_position_panel_enabled())
        self.assertTrue(load_position_panel_expanded())

    def test_position_config_defaults_roundtrip(self) -> None:
        save_watchlist_position_config(WatchlistPositionConfig())
        loaded = load_watchlist_position_config()
        self.assertTrue(loaded.follow_signal)
        self.assertEqual(loaded.fast_window, 10)
        self.assertEqual(loaded.slow_window, 20)

    def test_position_config_effective_follows_signal(self) -> None:
        pos = WatchlistPositionConfig(follow_signal=True)
        signal = WatchlistSignalConfig(
            class_name="AshareTrendMaStrategy",
            fast_window=5,
            slow_window=15,
        )
        effective = pos.effective_signal_config(signal)
        self.assertEqual(effective.class_name, "AshareTrendMaStrategy")
        self.assertEqual(effective.fast_window, 5)
        self.assertEqual(effective.slow_window, 15)

    def test_position_config_effective_uses_own_params(self) -> None:
        pos = WatchlistPositionConfig(follow_signal=False, fast_window=8, slow_window=18)
        signal = WatchlistSignalConfig(fast_window=5, slow_window=15)
        effective = pos.effective_signal_config(signal)
        self.assertEqual(effective.fast_window, 8)
        self.assertEqual(effective.slow_window, 18)


class PositionQuoteRefreshTests(unittest.TestCase):
    def test_refresh_quotes_only_updates_matching_symbols(self) -> None:
        from vnpy_ashare.domain.trading.position import PositionRecord, PositionSnapshot
        from vnpy_ashare.ui.quotes.watchlist_positions.controller import WatchlistPositionController

        class _Item:
            def __init__(self, tickflow_symbol: str) -> None:
                self.tickflow_symbol = tickflow_symbol

        class _Panel:
            def __init__(self) -> None:
                self.tickflow_calls: list[set[str]] = []
                self.render_calls = 0

            def update_rows_for_tickflow_symbols(self, tickflow_symbols: set[str]) -> None:
                self.tickflow_calls.append(set(tickflow_symbols))

            def render_panel(self) -> None:
                self.render_calls += 1

        class _Page:
            config = type("Cfg", (), {"show_watchlist_positions": True})()
            _active = True
            position_cache: dict = {}
            quote_map: dict = {}

            def find_stock_item(self, vt_symbol: str):
                return self._items.get(vt_symbol)

        page = _Page()
        page._items = {
            "600000.SSE": _Item("600000"),
            "000001.SZSE": _Item("000001"),
        }
        page.position_cache = {
            "600000.SSE": PositionSnapshot(
                vt_symbol="600000.SSE",
                name="浦发",
                cost_price=10.0,
                volume=100,
                buy_date="2026-06-01",
                source="manual",
                last_price=10.0,
                market_value=1000.0,
                unrealized_pnl=0.0,
                unrealized_pnl_pct=0.0,
                exit_signal="hold",
                signal_snapshot=None,
                t1_locked=False,
                exit_ref_price=None,
                dist_exit_pct=None,
                warnings=(),
            ),
        }
        panel = _Panel()
        page.position_panel = panel
        controller = WatchlistPositionController.__new__(WatchlistPositionController)
        controller._page = page
        controller._record_map = lambda: {
            "600000.SSE": PositionRecord(
                symbol="600000",
                exchange="SSE",
                name="浦发",
                cost_price=10.0,
                volume=100,
                buy_date="2026-06-01",
                source="manual",
            ),
            "000001.SZSE": PositionRecord(
                symbol="000001",
                exchange="SZSE",
                name="平安",
                cost_price=12.0,
                volume=100,
                buy_date="2026-06-01",
                source="manual",
            ),
        }
        controller._rebuild_cache_entry = lambda record, signal: None  # type: ignore[method-assign]
        controller._scan_position_alerts = lambda: None  # type: ignore[method-assign]

        tickflow = page._items["600000.SSE"].tickflow_symbol
        controller.refresh_quotes_only({tickflow})

        self.assertEqual(panel.render_calls, 0)
        self.assertEqual(panel.tickflow_calls, [{tickflow}])


class PositionDiskCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch(
            "vnpy_ashare.storage.cache.watchlist_position_cache._cache_db_path",
            return_value=self.db_path,
        )
        self._patcher.start()
        self.cache = WatchlistPositionDiskCache()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_roundtrip_with_position_key(self) -> None:
        snap = _sample_signal()
        self.cache.put(
            snap,
            config_key="AshareDoubleMaStrategy:10:20",
            bar_as_of="2026-06-10",
            position_key="10.5:100:2026-06-01",
        )
        loaded = self.cache.get(
            "600000.SSE",
            "AshareDoubleMaStrategy:10:20",
            "2026-06-10",
            "10.5:100:2026-06-01",
        )
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.signal, "sell")

    def test_miss_when_position_key_changes(self) -> None:
        snap = _sample_signal()
        self.cache.put(
            snap,
            config_key="AshareDoubleMaStrategy:10:20",
            bar_as_of="2026-06-10",
            position_key="10.5:100:2026-06-01",
        )
        self.assertIsNone(
            self.cache.get(
                "600000.SSE",
                "AshareDoubleMaStrategy:10:20",
                "2026-06-10",
                "11.0:200:2026-06-02",
            )
        )


if __name__ == "__main__":
    unittest.main()
