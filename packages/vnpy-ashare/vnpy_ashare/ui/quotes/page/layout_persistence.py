"""行情页 Splitter / 列配置持久化。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtGui

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.ui.quotes.watchlist_signals.splitter import apply_center_splitter_sizes, restore_center_splitter

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


def splitter_settings_key(page: QuotesPage) -> str:
    return f"quotes/splitter/{page.page_name}"


def save_splitter(page: QuotesPage) -> None:
    if page._splitter is None:
        return
    settings = get_settings()
    settings.setValue(splitter_settings_key(page), page._splitter.saveState())


def restore_splitter(page: QuotesPage) -> None:
    if page._splitter is None:
        return
    settings = get_settings()
    state = settings.value(splitter_settings_key(page))
    if state is not None:
        page._splitter.restoreState(state)


def schedule_center_splitter_layout(page: QuotesPage) -> None:
    if not (
        page.config.show_watchlist_signals
        or page.config.show_watchlist_positions
        or page.config.show_run_output_panel
    ):
        return
    QtCore.QTimer.singleShot(0, lambda: restore_center_splitter(page))
    QtCore.QTimer.singleShot(150, lambda: restore_center_splitter(page))


def on_quotes_page_resize(page: QuotesPage, _event: QtGui.QResizeEvent) -> None:
    if getattr(page, "_center_splitter", None) is not None:
        apply_center_splitter_sizes(page)
