"""本地 K 线变更后刷新自选策略面板。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


def refresh_watchlist_signals(page: QuotesPage, vt_symbols: list[str]) -> None:
    if not page.config.show_watchlist_signals:
        return
    page._signals.refresh_symbols(vt_symbols)


def refresh_watchlist_positions(page: QuotesPage, vt_symbols: list[str]) -> None:
    if not page.config.show_watchlist_positions:
        return
    page._positions.refresh_symbols(vt_symbols)


def position_vt_symbols(page: QuotesPage) -> list[str]:
    service = page._get_position_service()
    if service is None:
        return []
    return [record.vt_symbol for record in service.get_items()]


def refresh_watchlist_strategy_panels(page: QuotesPage, vt_symbols: list[str]) -> None:
    refresh_watchlist_signals(page, vt_symbols)
    refresh_watchlist_positions(page, vt_symbols)
