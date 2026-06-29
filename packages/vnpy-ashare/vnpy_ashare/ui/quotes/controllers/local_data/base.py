"""LocalDataController 共享状态。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.config.runtime import format_vt_symbol_cn
from vnpy_ashare.data.minute_periods import is_daily_scope, scope_display
from vnpy_ashare.ui.quotes.page.run_log import append_run_log

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

from vnpy_ashare.domain.symbols.stock import StockItem


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

    def should_auto_check_gaps(self) -> bool:
        """分页本地页不自动扫描断层，由用户通过补缺/断层修复按钮处理。"""
        page = self._p
        return (
            page.config.show_fill_button
            and self.is_daily_scope()
            and not page.config.use_local_pagination
        )

    def dismiss_gap_check(self) -> None:
        """翻页/重载列表时放弃进行中的断层扫描。"""
        page = self._p
        page._selected_gap_result = None
        page._gap_generation += 1
        if page._thread_active(getattr(page, "_gap_worker", None)):
            page._wait_worker_release("_gap_worker", timeout_ms=0)

    def abandon_bars_worker(self) -> None:
        """切换标的时不阻塞 UI，旧 K 线 Worker 后台结束即可。"""
        page = self._p
        if page._thread_active(getattr(page, "_bars_worker", None)):
            page._wait_worker_release("_bars_worker", timeout_ms=0)

    def set_kline_loading_status(self, item: StockItem) -> None:
        page = self._p
        if not page.config.use_local_table:
            return
        label = format_vt_symbol_cn(item.symbol, item.exchange)
        page.status_label.setText(f"正在加载 {label} {self.scope_label()}…")

    def restore_list_status(self) -> None:
        page = self._p
        if not page.config.use_local_table:
            return
        if page.config.use_local_pagination:
            page.status_label.setText(page._pagination.format_local_status())
            return
        table = getattr(page, "_table", None)
        if table is not None and hasattr(table, "update_display_status"):
            table.update_display_status()

    def _connect_worker_log(self, worker: QtCore.QThread) -> None:
        log_signal = getattr(worker, "log", None)
        if log_signal is not None:
            log_signal.connect(lambda message: append_run_log(self._p, message))
