"""行情页可取消后台任务与 busy 态 UI 锁定。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.config.trading_universe import is_market_board_combo_locked

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


def collect_busy_widgets(
    page: QuotesPage,
    *,
    lock_table: bool = True,
    lock_search: bool = True,
) -> list[QtWidgets.QWidget]:
    widgets: list[QtWidgets.QWidget] = []
    if lock_search:
        widgets.append(page.search_edit)
        if page.config.use_local_table:
            widgets.append(page.local_period_combo)
        if page.config.show_board_filter:
            widgets.append(page.board_combo)
        if page.industry_filter is not None:
            widgets.append(page.industry_filter)
        if page.config.use_market_rank or page.config.show_refresh_quotes_button:
            widgets.append(page.refresh_quotes_button)
        if page.config.show_sync_button:
            widgets.append(page.sync_button)
        if lock_table and page.config.use_market_rank and not page.config.market_full_list:
            for name in (
                "home_button",
                "prev_page_button",
                "next_page_button",
                "end_button",
                "page_jump_input",
            ):
                control = getattr(page, name, None)
                if control is not None:
                    widgets.append(control)
    for name in (
        "download_button",
        "fill_button",
        "redownload_button",
        "delete_local_button",
        "batch_fill_button",
        "batch_gap_fill_button",
        "gap_fill_button",
        "add_watchlist_button",
        "remove_watchlist_button",
        "backtest_button",
        "batch_backtest_button",
        "diagnose_button",
    ):
        button = getattr(page, name, None)
        if button is not None:
            widgets.append(button)
    if lock_table and page.config.use_market_rank and not page.config.market_full_list:
        for name in (
            "home_button",
            "prev_page_button",
            "next_page_button",
            "end_button",
            "page_jump_input",
        ):
            control = getattr(page, name, None)
            if control is not None:
                widgets.append(control)
    return widgets


def set_busy(
    page: QuotesPage,
    busy: bool,
    *,
    lock_table: bool = True,
    lock_search: bool = True,
) -> None:
    if lock_search:
        page.search_edit.setEnabled(not busy)
        if page.config.use_local_table:
            page.local_period_combo.setEnabled(not busy)
        if page.config.show_board_filter:
            page.board_combo.setEnabled(not busy and not is_market_board_combo_locked())
        if page.industry_filter is not None:
            page.industry_filter.setEnabled(not busy)
        rank_list = getattr(page, "rank_list", None)
        if rank_list is not None:
            rank_list.setEnabled(not busy)
        if page.config.use_market_rank or page.config.show_refresh_quotes_button:
            page.refresh_quotes_button.setEnabled(not busy)
        if page.config.show_sync_button:
            page.sync_button.setEnabled(not busy)
        if lock_table and page.config.use_market_rank and not page.config.market_full_list:
            page._pagination.update_busy_state(busy)
    if busy:
        if page.config.show_download_button:
            page.download_button.setEnabled(False)
        if page.config.show_fill_button:
            page.fill_button.setEnabled(False)
        if page.config.show_redownload_button:
            page.redownload_button.setEnabled(False)
        if page.config.show_delete_button:
            page.delete_local_button.setEnabled(False)
        if page.config.show_batch_fill_button:
            page.batch_fill_button.setEnabled(False)
        if page.config.show_batch_gap_fill_button:
            page.batch_gap_fill_button.setEnabled(False)
            page.gap_fill_button.setEnabled(False)
        if page.config.show_add_watchlist_button:
            page.add_watchlist_button.setEnabled(False)
        if page.config.show_remove_watchlist_button:
            page.remove_watchlist_button.setEnabled(False)
    else:
        page._update_action_buttons()
    if lock_table:
        page.market_table.setEnabled(not busy)


def begin_cancellable_task(
    page: QuotesPage,
    message: str,
    *,
    worker_attr: str,
    primary: QtWidgets.QPushButton | None = None,
    primary_text: str = "",
    primary_handler=None,
    lock_table: bool = True,
    lock_search: bool = True,
) -> None:
    page._active_worker_attr = worker_attr
    page._task_lock_table = lock_table
    page._task_lock_search = lock_search
    set_busy(page, True, lock_table=lock_table, lock_search=lock_search)

    def on_cancel() -> None:
        worker = getattr(page, worker_attr, None)
        if worker is not None and hasattr(worker, "request_cancel"):
            worker.request_cancel()

    page._task_guard.begin(
        message,
        widgets=collect_busy_widgets(page, lock_table=lock_table, lock_search=lock_search),
        primary=primary,
        primary_text=primary_text,
        primary_handler=primary_handler,
        on_cancel=on_cancel,
    )


def end_cancellable_task(page: QuotesPage) -> bool:
    cancelled = page._task_guard.cancelled
    page._task_guard.end()
    set_busy(
        page,
        False,
        lock_table=page._task_lock_table,
        lock_search=getattr(page, "_task_lock_search", True),
    )
    page._active_worker_attr = None
    return cancelled


def finish_cancellable_task(page: QuotesPage, *, cancelled_message: str = "任务已取消") -> bool:
    if end_cancellable_task(page):
        page._toast.info(cancelled_message)
        return True
    return False
