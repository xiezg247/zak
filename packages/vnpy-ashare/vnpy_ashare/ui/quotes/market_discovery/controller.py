"""市场页异动带控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.domain.market_hours import is_ashare_trading_session
from vnpy_ashare.ui.quotes.market_discovery.worker import MarketDiscoveryLoadWorker
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.market_discovery.panel import MarketDiscoveryStrip
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

REFRESH_MS = 60_000


class MarketDiscoveryController(QtCore.QObject):
    def __init__(self, page: QuotesPage, strip: MarketDiscoveryStrip) -> None:
        super().__init__(page)
        self._page = page
        self._strip = strip
        self._worker: MarketDiscoveryLoadWorker | None = None
        self._retired_workers: list[QtCore.QThread] = []
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setInterval(REFRESH_MS)
        self._refresh_timer.timeout.connect(self.refresh)
        self._session_timer = QtCore.QTimer(self)
        self._session_timer.setInterval(30_000)
        self._session_timer.timeout.connect(self._on_session_tick)

        strip.row_activated.connect(self._on_row_activated)

    def activate(self) -> None:
        QtCore.QTimer.singleShot(800, self.refresh)
        self._schedule_timer()
        self._session_timer.start()

    def deactivate(self) -> None:
        self._refresh_timer.stop()
        self._session_timer.stop()
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.request_cancel()
        release_thread(self._retired_workers, worker, timeout_ms=0)

    def _on_session_tick(self) -> None:
        self._schedule_timer()

    def _schedule_timer(self) -> None:
        if is_ashare_trading_session():
            self._refresh_timer.start()
        else:
            self._refresh_timer.stop()

    def refresh(self) -> None:
        if thread_is_active(self._worker):
            return
        worker = MarketDiscoveryLoadWorker(parent=self._page)
        self._worker = worker
        self._strip.set_loading(True)

        def on_finished(volume, moneyflow) -> None:
            if self._worker is worker:
                self._worker = None
            release_thread(self._retired_workers, worker)
            self._strip.apply_cards(volume, moneyflow)

        def on_failed(message: str) -> None:
            if self._worker is worker:
                self._worker = None
            release_thread(self._retired_workers, worker)
            self._strip.apply_cards(None, None)
            page_notify(self._page, f"异动带加载失败：{message}", level="warning")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def _on_row_activated(self, vt_symbol: str) -> None:
        if self._page._table.focus_market_symbol(vt_symbol):
            self._page.status_label.setText(f"已定位：{vt_symbol}")
            return
        page_notify(self._page, f"主表中未找到：{vt_symbol}", level="warning")
