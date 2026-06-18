"""自选页信号/持仓策略刷新：单 Timer 驱动双 controller。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.ui.quotes.page.config import WATCHLIST_SIGNAL_REFRESH_MS

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage
    from vnpy_ashare.ui.quotes.watchlist_positions.controller import WatchlistPositionController
    from vnpy_ashare.ui.quotes.watchlist_signals.controller import WatchlistSignalController


class WatchlistStrategyRefreshScheduler:
    """合并 signal / position 定时刷新，避免双 QTimer 同频触发。"""

    def __init__(
        self,
        page: QuotesPage,
        signals: WatchlistSignalController,
        positions: WatchlistPositionController,
    ) -> None:
        self._page = page
        self._signals = signals
        self._positions = positions
        self._timer = QtCore.QTimer(page)
        self._timer.timeout.connect(self._on_tick)

    def start(self) -> None:
        cfg = self._page.config
        if not (cfg.show_watchlist_signals or cfg.show_watchlist_positions):
            return
        self._timer.setInterval(WATCHLIST_SIGNAL_REFRESH_MS)
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _on_tick(self) -> None:
        self._signals.refresh(force=False)
        self._positions.refresh(force=False)
