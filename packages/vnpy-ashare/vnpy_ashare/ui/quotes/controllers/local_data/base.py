"""LocalDataController 共享状态。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.data.minute_periods import is_daily_scope, scope_display
from vnpy_ashare.ui.quotes.page.run_log import append_run_log

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


class LocalDataControllerBase:
    def __init__(self, page: QuotesPage) -> None:
        self._page = page

    @property
    def _p(self) -> QuotesPage:
        return self._page

    def is_daily_scope(self) -> bool:
        page = self._p
        return not page.config.use_local_table or is_daily_scope(page._local_scope)

    def scope_label(self) -> str:
        return scope_display(self._p._local_scope)

    def _connect_worker_log(self, worker: QtCore.QThread) -> None:
        log_signal = getattr(worker, "log", None)
        if log_signal is not None:
            log_signal.connect(lambda message: append_run_log(self._p, message))
