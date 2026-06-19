"""WatchlistStrategyRefreshScheduler 单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from vnpy.trader.ui import QtWidgets

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ui.quotes.page.config import WATCHLIST_SIGNAL_REFRESH_MS
from vnpy_ashare.ui.quotes.watchlist.refresh_scheduler import WatchlistStrategyRefreshScheduler


class WatchlistStrategyRefreshSchedulerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _make_scheduler(self, *, signals: bool, positions: bool):
        page = QtWidgets.QWidget()
        page.config = MagicMock()
        page.config.show_watchlist_signals = signals
        page.config.show_watchlist_positions = positions
        signals_ctrl = MagicMock()
        positions_ctrl = MagicMock()
        scheduler = WatchlistStrategyRefreshScheduler(page, signals_ctrl, positions_ctrl)
        return scheduler, signals_ctrl, positions_ctrl

    def test_start_uses_single_timer_when_signals_or_positions_enabled(self) -> None:
        scheduler, _, _ = self._make_scheduler(signals=True, positions=False)

        scheduler.start()

        self.assertTrue(scheduler._timer.isActive())
        self.assertEqual(scheduler._timer.interval(), WATCHLIST_SIGNAL_REFRESH_MS)

    def test_start_noop_when_both_disabled(self) -> None:
        scheduler, _, _ = self._make_scheduler(signals=False, positions=False)

        scheduler.start()

        self.assertFalse(scheduler._timer.isActive())

    def test_tick_refreshes_both_controllers(self) -> None:
        scheduler, signals, positions = self._make_scheduler(signals=True, positions=True)

        scheduler._on_tick()

        signals.refresh.assert_called_once_with(force=False)
        positions.refresh.assert_called_once_with(force=False)

    def test_stop_halts_timer(self) -> None:
        scheduler, _, _ = self._make_scheduler(signals=True, positions=True)
        scheduler.start()

        scheduler.stop()

        self.assertFalse(scheduler._timer.isActive())


if __name__ == "__main__":
    unittest.main()
