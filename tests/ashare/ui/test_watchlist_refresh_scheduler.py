"""WatchlistStrategyStaleSweep 单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy.trader.ui import QtWidgets

import tests._bootstrap  # noqa: F401
from vnpy_ashare.config.preferences.watchlist_signal import (
    DEFAULT_STALE_SWEEP_MINUTES,
    load_watchlist_strategy_stale_sweep_minutes,
    save_watchlist_strategy_stale_sweep_minutes,
)
from vnpy_ashare.ui.quotes.page.config import WATCHLIST_STRATEGY_SESSION_TICK_MS
from vnpy_ashare.ui.quotes.watchlist.refresh_scheduler import WatchlistStrategyStaleSweep


class WatchlistStrategyStaleSweepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _make_sweep(self, *, signals: bool, positions: bool, active: bool = True):
        page = QtWidgets.QWidget()
        page.config = MagicMock()
        page.config.show_watchlist_signals = signals
        page.config.show_watchlist_positions = positions
        page._active = active
        page._strategy_batch = MagicMock()
        page._strategy_batch.is_busy.return_value = False
        signals_ctrl = MagicMock()
        positions_ctrl = MagicMock()
        sweep = WatchlistStrategyStaleSweep(page, signals_ctrl, positions_ctrl)
        return sweep, page, signals_ctrl, positions_ctrl

    def test_start_noop_when_both_disabled(self) -> None:
        sweep, _, signals, positions = self._make_sweep(signals=False, positions=False)

        sweep.start()

        self.assertFalse(sweep._sweep_timer.isActive())
        self.assertFalse(sweep._session_timer.isActive())
        signals.refresh.assert_not_called()
        positions.refresh.assert_not_called()

    @patch("vnpy_ashare.ui.quotes.watchlist.refresh_scheduler.is_ashare_trading_session", return_value=True)
    def test_start_starts_sweep_timer_during_trading_session(self, _session: MagicMock) -> None:
        sweep, _, _, _ = self._make_sweep(signals=True, positions=False)
        save_watchlist_strategy_stale_sweep_minutes(DEFAULT_STALE_SWEEP_MINUTES)

        sweep.start()

        self.assertTrue(sweep._sweep_timer.isActive())
        expected_ms = load_watchlist_strategy_stale_sweep_minutes() * 60 * 1000
        self.assertEqual(sweep._sweep_timer.interval(), expected_ms)
        self.assertTrue(sweep._session_timer.isActive())
        self.assertEqual(sweep._session_timer.interval(), WATCHLIST_STRATEGY_SESSION_TICK_MS)

    @patch("vnpy_ashare.ui.quotes.watchlist.refresh_scheduler.is_ashare_trading_session", return_value=False)
    def test_start_does_not_start_sweep_timer_off_session(self, _session: MagicMock) -> None:
        sweep, _, signals, positions = self._make_sweep(signals=True, positions=True)

        sweep.start()

        self.assertFalse(sweep._sweep_timer.isActive())
        signals.refresh.assert_not_called()
        positions.refresh.assert_not_called()

    def test_on_sweep_refreshes_both_controllers(self) -> None:
        sweep, _, signals, positions = self._make_sweep(signals=True, positions=True)

        sweep._on_sweep()

        signals.refresh.assert_called_once_with(force=False)
        positions.refresh.assert_called_once_with(force=False)

    def test_on_sweep_skips_when_batch_busy(self) -> None:
        sweep, page, signals, positions = self._make_sweep(signals=True, positions=True)
        page._strategy_batch.is_busy.return_value = True

        sweep._on_sweep()

        signals.refresh.assert_not_called()
        positions.refresh.assert_not_called()

    def test_reapply_interval_reads_settings(self) -> None:
        sweep, _, _, _ = self._make_sweep(signals=True, positions=True)
        save_watchlist_strategy_stale_sweep_minutes(45)

        sweep.reapply_interval()

        self.assertEqual(sweep._sweep_timer.interval(), 45 * 60 * 1000)

    @patch("vnpy_ashare.ui.quotes.watchlist.refresh_scheduler.is_ashare_trading_session", return_value=True)
    def test_stop_halts_timers(self, _session: MagicMock) -> None:
        sweep, _, _, _ = self._make_sweep(signals=True, positions=True)
        sweep.start()

        sweep.stop()

        self.assertFalse(sweep._sweep_timer.isActive())
        self.assertFalse(sweep._session_timer.isActive())


if __name__ == "__main__":
    unittest.main()
