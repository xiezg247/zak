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


def navigate_to_strategy_monitor(start: QtWidgets.QWidget) -> QuotesPage | None:
    from vnpy_ashare.ui.shell.main_window_pages import (
        _switch_page_deferred,
        get_or_create_page,
        nav_index_for_key,
        show_page_by_key,
    )

    win = find_ashare_main_window(start)
    if win is None:
        return None

    nav_index = nav_index_for_key(win, STRATEGY_MONITOR_NAV_KEY)
    widget = win._page_widgets.get(STRATEGY_MONITOR_NAV_KEY)
    if widget is None:
        if nav_index is not None:
            win.sidebar.set_active_index(nav_index)
        widget = get_or_create_page(win, STRATEGY_MONITOR_NAV_KEY)
        if widget is None:
            return None
        _switch_page_deferred(
            win,
            widget,
            key=STRATEGY_MONITOR_NAV_KEY,
            old_key=win._current_key,
            nav_index=nav_index,
        )
    else:
        show_page_by_key(win, STRATEGY_MONITOR_NAV_KEY, nav_index=nav_index)

    if hasattr(widget, "page"):
        return widget.page
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
    return added, skipped


def focus_watchlist_symbol_from_page(page: QuotesPage, vt_symbol: str) -> None:
    from vnpy_ashare.ui.shell.main_window_navigation import focus_watchlist_symbol

    item = page.find_stock_item(vt_symbol)
    if item is None:
        return
    win = find_ashare_main_window(as_qwidget(page))
    if win is None:
        return
    focus_watchlist_symbol(win, item.symbol, item.exchange.name)
