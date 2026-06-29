"""自选页标的列表行情加载状态（底栏 status_label）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.ui.quotes.page.roles import WATCHLIST_PAGE

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

LOADING_SUFFIX = " · 获取数据中…"


def is_watchlist_quote_table_page(page: QuotesPage) -> bool:
    return page.page_name == WATCHLIST_PAGE and page.config.scope_key == "自选池"


def display_quotes_pending(page: QuotesPage) -> bool:
    if not page.display_stocks:
        return False
    return any(item.tickflow_symbol not in page.quote_map for item in page.display_stocks)


def should_show_quotes_loading(page: QuotesPage) -> bool:
    if not is_watchlist_quote_table_page(page) or not page._active:
        return False
    if getattr(page, "_watchlist_quotes_loading", False):
        return True
    return page.config.use_quote_stream and display_quotes_pending(page)


def append_loading_suffix(page: QuotesPage, status: str) -> str:
    if should_show_quotes_loading(page):
        return f"{status}{LOADING_SUFFIX}"
    return status


def begin_watchlist_quotes_fetch(page: QuotesPage) -> None:
    if not is_watchlist_quote_table_page(page):
        return
    page._watchlist_quotes_loading = True
    refresh_watchlist_quotes_status(page)


def end_watchlist_quotes_fetch(page: QuotesPage) -> None:
    if not is_watchlist_quote_table_page(page):
        return
    page._watchlist_quotes_loading = False
    refresh_watchlist_quotes_status(page)


def refresh_watchlist_quotes_status(page: QuotesPage) -> None:
    table = getattr(page, "_table", None)
    if table is not None and hasattr(table, "update_display_status"):
        table.update_display_status()
