"""自选页策略 stale 巡检：低频补算，与行情定时器分离。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.config.preferences.watchlist_signal import load_watchlist_strategy_stale_sweep_ms
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.ui.quotes.page.config import WATCHLIST_STRATEGY_SESSION_TICK_MS

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage
    from vnpy_ashare.ui.quotes.watchlist_positions.controller import WatchlistPositionController
    from vnpy_ashare.ui.quotes.watchlist_signals.controller import WatchlistSignalController


def _strategy_runtime_active(page: QuotesPage) -> bool:
    from vnpy_ashare.ui.quotes.features.watchlist.strategy_workspace import is_strategy_workspace_open
    from vnpy_ashare.ui.quotes.page.roles import is_strategy_monitor_page

    if is_strategy_monitor_page(page.page_name):
        return True
    return is_strategy_workspace_open(page)


class WatchlistStrategyStaleSweep(QtCore.QObject):
    """交易时段内低频巡检 signal/position 是否 stale，仅 `refresh(force=False)`。"""

    _ACTIVATE_SWEEP_DELAY_MS = 800

    def __init__(
        self,
        page: QuotesPage,
        signals: WatchlistSignalController,
        positions: WatchlistPositionController,
    ) -> None:
        super().__init__(page)
        self._page = page
        self._signals = signals
        self._positions = positions
        self._sweep_timer = QtCore.QTimer(self)
        self._sweep_timer.timeout.connect(self._on_sweep)
        self._session_timer = QtCore.QTimer(self)
        self._session_timer.setInterval(WATCHLIST_STRATEGY_SESSION_TICK_MS)
        self._session_timer.timeout.connect(self._schedule_sweep)
        self.reapply_interval()

    def reapply_interval(self) -> None:
        self._sweep_timer.setInterval(load_watchlist_strategy_stale_sweep_ms())

    def start(self) -> None:
        cfg = self._page.config
        if not (cfg.show_watchlist_signals or cfg.show_watchlist_positions):
            return
        if not _strategy_runtime_active(self._page):
            return
        self.reapply_interval()
        self._schedule_sweep()
        self._session_timer.start()
        if is_ashare_trading_session():
            QtCore.QTimer.singleShot(self._ACTIVATE_SWEEP_DELAY_MS, self._on_sweep)

    def stop(self) -> None:
        self._sweep_timer.stop()
        self._session_timer.stop()

    def _schedule_sweep(self) -> None:
        if not getattr(self._page, "_active", False):
            self._sweep_timer.stop()
            return
        cfg = self._page.config
        if not (cfg.show_watchlist_signals or cfg.show_watchlist_positions):
            self._sweep_timer.stop()
            return
        if not _strategy_runtime_active(self._page):
            self._sweep_timer.stop()
            return
        if is_ashare_trading_session():
            if not self._sweep_timer.isActive():
                self._sweep_timer.start()
        else:
            self._sweep_timer.stop()

    def _on_sweep(self) -> None:
        if not getattr(self._page, "_active", False):
            return
        if not _strategy_runtime_active(self._page):
            return
        batch = getattr(self._page, "_strategy_batch", None)
        if batch is not None and batch.is_busy():
            return
        cfg = self._page.config
        if cfg.show_watchlist_positions:
            self._positions.refresh(force=False)


WatchlistStrategyRefreshScheduler = WatchlistStrategyStaleSweep
