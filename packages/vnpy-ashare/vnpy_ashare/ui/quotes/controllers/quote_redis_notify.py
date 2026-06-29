"""Redis Pub/Sub 行情更新 → 主线程增量刷新。"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.quotes.core.quote_l1_cache import clear_quote_l1_cache, quote_l1_enabled
from vnpy_ashare.quotes.core.quote_notify import quote_redis_notify_enabled, run_quote_notify_listener
from vnpy_ashare.ui.quotes.page.quote_refresh import quote_auto_refresh_enabled

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


class QuoteRedisNotifyController:
    """订阅 ``zak:notify:quotes``，collect 完成后触发去抖刷新。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_seq = 0

    def start(self) -> None:
        page = self._page
        if not quote_redis_notify_enabled() or not page.config.quote_source:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._listen,
            name="quote-redis-notify",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread = None
        self._last_seq = 0

    def _listen(self) -> None:
        run_quote_notify_listener(
            on_seq=self._dispatch_seq,
            stop=self._stop,
        )

    def _dispatch_seq(self, seq: int) -> None:
        if seq <= 0 or seq == self._last_seq:
            return
        self._last_seq = seq
        QtCore.QTimer.singleShot(0, lambda: self._on_seq(seq))

    def _on_seq(self, seq: int) -> None:
        page = self._page
        if not page._active or not quote_auto_refresh_enabled(page):
            return
        if quote_l1_enabled():
            clear_quote_l1_cache()
        from vnpy_ashare.quotes.core.market_snapshot_hub import clear_process_quote_snapshot
        from vnpy_ashare.quotes.core.quote_rows import clear_market_quote_rows_cache

        clear_process_quote_snapshot()
        clear_market_quote_rows_cache()
        page._actions.refresh_quotes_rest()
