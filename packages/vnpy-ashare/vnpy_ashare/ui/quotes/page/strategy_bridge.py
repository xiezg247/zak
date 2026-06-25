"""自选页与策略监控页之间的导航与数据桥接。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.ui.quotes._host_widget import as_qwidget
from vnpy_ashare.ui.quotes.page.roles import STRATEGY_MONITOR_NAV_KEY
from vnpy_ashare.ui.shell.main_window_lookup import find_ashare_main_window

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


def _strategy_monitor_page_widget(win: QtWidgets.QWidget):
    from vnpy_ashare.ui.shell.main_window_pages import get_or_create_page

    return get_or_create_page(win, STRATEGY_MONITOR_NAV_KEY)


def navigate_to_strategy_monitor(start: QtWidgets.QWidget) -> QuotesPage | None:
    win = find_ashare_main_window(start)
    if win is None:
        return None
    from vnpy_ashare.ui.shell.main_window_pages import nav_index_for_key, show_page_by_key

    nav_index = nav_index_for_key(win, STRATEGY_MONITOR_NAV_KEY)
    show_page_by_key(win, STRATEGY_MONITOR_NAV_KEY, nav_index=nav_index)
    widget = _strategy_monitor_page_widget(win)
    if widget is not None and hasattr(widget, "page"):
        page = widget.page
        if hasattr(page, "activate"):
            page.activate()
        return page
    return None


def add_items_to_strategy_monitor(start: QtWidgets.QWidget, items: list[StockItem]) -> tuple[int, int]:
    """从自选页将标的加入策略监控信号区；必要时先切页。"""
    page = navigate_to_strategy_monitor(start)
    if page is None:
        return 0, len(items)
    panel = getattr(page, "signal_panel", None)
    if panel is None:
        return 0, len(items)
    added, skipped = panel.add_symbols([item.vt_symbol for item in items])
    if added:
        page._signals.refresh(force=True)
    return added, skipped


def focus_watchlist_symbol_from_page(page: QuotesPage, vt_symbol: str) -> None:
    item = page.find_stock_item(vt_symbol)
    if item is None:
        return
    win = find_ashare_main_window(as_qwidget(page))
    if win is None:
        return
    from vnpy_ashare.ui.shell.main_window_navigation import focus_watchlist_symbol

    focus_watchlist_symbol(win, item.symbol, item.exchange.name)
