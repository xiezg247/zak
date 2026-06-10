"""自选页策略信号批量刷新。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.ui.quotes.watchlist_signal_settings import (
    WatchlistSignalConfig,
    save_watchlist_signal_config,
)

if TYPE_CHECKING:
    from vnpy_ashare.services.analysis_service import AnalysisService
    from vnpy_ashare.ui.quotes.quotes_page import QuotesPage


class WatchlistSignalController:
    """自选池策略信号：后台批量计算 + 定时刷新。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page
        self._worker: QtCore.QThread | None = None
        self._timer = QtCore.QTimer(page)
        self._timer.timeout.connect(lambda: self.refresh(force=False))

    def _enabled(self) -> bool:
        return self._page.config.show_watchlist_signals and self._page.page_name == "自选"

    def _analysis_service(self) -> AnalysisService | None:
        return self._page._get_analysis_service()

    def start(self) -> None:
        if not self._enabled():
            return
        from vnpy_ashare.ui.quotes.quotes_config import WATCHLIST_SIGNAL_REFRESH_MS

        self._timer.setInterval(WATCHLIST_SIGNAL_REFRESH_MS)
        self.refresh(force=True)
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        worker = self._worker
        if worker is not None:
            self._worker = None
            from vnpy_common.ui.qt_helpers import release_thread

            release_thread(self._page._retired_workers, worker, timeout_ms=0)

    def apply_config(self, config: WatchlistSignalConfig, *, save: bool = True) -> None:
        normalized = config.normalized()
        if self._page.signal_config == normalized:
            return
        if save:
            save_watchlist_signal_config(normalized)
        self._page.signal_config = normalized
        self.invalidate_cache()
        self.refresh(force=True)

    def refresh(self, *, force: bool = False) -> None:
        if not self._enabled() or not self._page._active:
            return
        if self._worker is not None and self._worker.isRunning():
            return

        service = self._analysis_service()
        if service is None:
            return

        items = list(self._page.display_stocks)
        if not items:
            self._page.signal_cache.clear()
            self._page._signal_cache_config = None
            return

        symbols = [item.vt_symbol for item in items]
        if not force and self._cache_covers(symbols):
            return

        config = self._page.signal_config.normalized()
        from vnpy_ashare.ui.quotes.workers.quotes_workers import WatchlistSignalWorker

        worker = WatchlistSignalWorker(
            service,
            symbols=symbols,
            class_name=config.class_name,
            fast_window=config.fast_window,
            slow_window=config.slow_window,
            parent=self._page,
        )
        self._worker = worker

        def on_finished(cache: dict) -> None:
            if self._worker is worker:
                self._worker = None
            if not self._page._active:
                return
            self._page.signal_cache.update(cache)
            self._page._signal_cache_config = config
            self._page._refresh_table_quotes()
            self._page._table.update_stats()
            item = self._page.current_item
            if item is not None and self._page.chart_panel is not None:
                snap = cache.get(item.vt_symbol)
                if snap is not None:
                    self._page.chart_panel.apply_signal_reference(snap)

        def on_failed(_msg: str) -> None:
            if self._worker is worker:
                self._worker = None

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def _cache_covers(self, symbols: list[str]) -> bool:
        cache = self._page.signal_cache
        if not cache:
            return False
        expected_config = self._page.signal_config.normalized()
        if self._page._signal_cache_config != expected_config:
            return False
        expected_strategy = expected_config.class_name
        for symbol in symbols:
            snap = cache.get(symbol)
            if snap is None or snap.strategy_id != expected_strategy:
                return False
        return True

    def invalidate_cache(self) -> None:
        self._page.signal_cache.clear()
        self._page._signal_cache_config = None
