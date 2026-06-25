"""主窗口页面缓存、创建与后台对话框。"""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ai.ui.page import AiPageWidget
from vnpy_ashare.app.deferred_apps import ensure_cta_backtester_app, ensure_data_manager_app
from vnpy_ashare.ui.backtest.pages.batch_backtest_page import BatchBacktestPageWidget
from vnpy_ashare.ui.features.info_feed.page import InfoFeedPageWidget
from vnpy_ashare.ui.features.notes_center.open import show_notes_center_dialog
from vnpy_ashare.ui.home.page import HomePageWidget
from vnpy_ashare.ui.scheduler.dialog import show_scheduler_dialog
from vnpy_ashare.ui.screener.pages.screener_hub_page import ScreenerHubPageWidget
from vnpy_ashare.ui.sector_flow.page import SectorFlowPageWidget
from vnpy_ashare.ui.shell.local.dialog import show_local_data_dialog
from vnpy_ashare.ui.shell.deferred_idle import touch_user_activity
from vnpy_ashare.ui.shell.manager.dialog import show_data_manager_dialog
from vnpy_ashare.ui.shell.page_shell import MarketPageWidget, RadarPageWidget, StrategyMonitorPageWidget, WatchlistPageWidget
from vnpy_common.ui.theme.build_extra import build_info_feed_stylesheet

if TYPE_CHECKING:
    from vnpy_ashare.ui.shell.main_window import AshareMainWindow

_QuotesPageFactory = Callable[[MainEngine, EventEngine], QtWidgets.QWidget]

QUOTES_WIDGETS: dict[str, _QuotesPageFactory] = {
    "market": MarketPageWidget,
    "sector_flow": SectorFlowPageWidget,
    "radar": RadarPageWidget,
    "watchlist": WatchlistPageWidget,
    "strategy_monitor": StrategyMonitorPageWidget,
}

SHELL_PAGE_WIDGETS: dict[str, _QuotesPageFactory] = {
    "home": HomePageWidget,
}

DEFERRED_CTA_PAGE_KEY = "cta_backtest"

VNPY_WIDGETS: dict[str, tuple[str, str]] = {
    "cta_backtest": ("vnpy_ashare.ui.backtest.pages.backtest_widget", "BacktesterWidget"),
}


def nav_index_for_key(win: AshareMainWindow, key: str) -> int | None:
    from vnpy_ashare.ui.shell.nav import APP_NAV_ENTRIES

    for index, entry in enumerate(APP_NAV_ENTRIES):
        if entry.key == key:
            return index
    return None


def get_or_create_page(win: AshareMainWindow, key: str) -> QtWidgets.QWidget | None:
    if key == DEFERRED_CTA_PAGE_KEY:
        ensure_cta_backtester_app(win.main_engine)
    if key in win._page_widgets:
        return win._page_widgets[key]

    widget: QtWidgets.QWidget | None = None

    if key in QUOTES_WIDGETS:
        widget = QUOTES_WIDGETS[key](win.main_engine, win.event_engine)
    elif key in SHELL_PAGE_WIDGETS:
        widget = SHELL_PAGE_WIDGETS[key](win.main_engine, win.event_engine)
    elif key in VNPY_WIDGETS:
        module_path, class_name = VNPY_WIDGETS[key]
        ui_module: ModuleType = import_module(module_path)
        widget_class = getattr(ui_module, class_name)
        widget = widget_class(win.main_engine, win.event_engine)
    elif key == "ai_assistant":
        page = AiPageWidget(win.main_engine, win.event_engine)
        page.collapse_to_dock.connect(win._return_to_floating_mode)
        widget = page
    elif key == "screener":
        widget = ScreenerHubPageWidget(win.main_engine, win.event_engine)
        widget.open_scheduler_requested.connect(lambda: open_scheduler_dialog(win))
    elif key == "info_feed":
        widget = InfoFeedPageWidget(win.main_engine, win.event_engine)
    elif key == "batch_backtest":
        widget = BatchBacktestPageWidget(win.main_engine, win.event_engine)

    if widget is not None:
        win._page_widgets[key] = widget
        win.widgets[key] = widget
        page_extra = build_info_feed_stylesheet if key == "info_feed" else ""
        win._theme_manager.bind_stylesheet(widget, extra=page_extra)

    return widget


def _finalize_page_switch(
    win: AshareMainWindow,
    *,
    widget: QtWidgets.QWidget,
    key: str,
    nav_index: int | None,
) -> None:
    win._current_key = key
    if key != "ai_assistant" and nav_index is not None:
        win._page_before_ai = nav_index
    if win._floating_controller is not None:
        win._floating_controller.on_page_changed(key)
        win._floating_controller.raise_floating_layers()


_DEFERRED_SWITCH_KEYS = frozenset({"watchlist", "strategy_monitor", "radar"})


def _switch_page_deferred(
    win: AshareMainWindow,
    widget: QtWidgets.QWidget,
    *,
    key: str,
    old_key: str | None,
    nav_index: int | None,
) -> None:
    """先切页并显示加载态，下一帧再 deactivate/activate，避免侧栏切换卡顿。"""
    if win.stack.indexOf(widget) < 0:
        win.stack.addWidget(widget)
    win.stack.setCurrentWidget(widget)
    if nav_index is not None:
        win.sidebar.set_active_index(nav_index)
    page = getattr(widget, "page", None)
    if page is not None and hasattr(page, "begin_tab_switch_loading"):
        page.begin_tab_switch_loading()
    win.raise_()
    win.activateWindow()

    def _complete() -> None:
        if old_key and old_key != key:
            old = win._page_widgets.get(old_key)
            if old is not None and hasattr(old, "deactivate"):
                old.deactivate()
        if hasattr(widget, "activate"):
            widget.activate()
        _finalize_page_switch(win, widget=widget, key=key, nav_index=nav_index)

    QtCore.QTimer.singleShot(0, _complete)


def _switch_watchlist_deferred(
    win: AshareMainWindow,
    widget: QtWidgets.QWidget,
    *,
    key: str,
    old_key: str | None,
    nav_index: int | None,
) -> None:
    _switch_page_deferred(win, widget, key=key, old_key=old_key, nav_index=nav_index)


def show_page_by_key(win: AshareMainWindow, key: str, *, nav_index: int | None = None) -> None:
    touch_user_activity(win)
    if key == "ai_assistant":
        if win._current_key and win._current_key != "ai_assistant":
            prev_index = nav_index_for_key(win, win._current_key)
            if prev_index is not None:
                win._page_before_ai = prev_index
        if win._floating_controller is not None:
            win._floating_controller.on_ai_assistant_entered()

    old_key = win._current_key
    if key in _DEFERRED_SWITCH_KEYS:
        widget = win._page_widgets.get(key)
        if widget is None:
            if nav_index is not None:
                win.sidebar.set_active_index(nav_index)

            def _create_and_switch() -> None:
                created = get_or_create_page(win, key)
                if created is None:
                    return
                _switch_page_deferred(win, created, key=key, old_key=old_key, nav_index=nav_index)

            QtCore.QTimer.singleShot(0, _create_and_switch)
            return
        _switch_page_deferred(win, widget, key=key, old_key=old_key, nav_index=nav_index)
        return

    widget = get_or_create_page(win, key)
    if widget is None:
        return

    if old_key and old_key != key:
        old = win._page_widgets.get(old_key)
        if old is not None and hasattr(old, "deactivate"):
            old.deactivate()

    if win.stack.indexOf(widget) < 0:
        win.stack.addWidget(widget)
    win.stack.setCurrentWidget(widget)

    if hasattr(widget, "activate"):
        widget.activate()

    _finalize_page_switch(win, widget=widget, key=key, nav_index=nav_index)
    if nav_index is not None:
        win.sidebar.set_active_index(nav_index)
    win.raise_()
    win.activateWindow()


def open_backstage_dialog(win: AshareMainWindow, key: str) -> None:
    if key == "scheduler":
        open_scheduler_dialog(win)
    elif key == "data_manager":
        open_data_manager_dialog(win)
    elif key == "local":
        open_local_data_dialog(win)


def open_scheduler_dialog(win: AshareMainWindow) -> None:
    show_scheduler_dialog(win.main_engine, win.event_engine, parent=win)


def open_local_data_dialog(win: AshareMainWindow) -> None:
    show_local_data_dialog(win.main_engine, win.event_engine, parent=win)


def open_data_manager_dialog(win: AshareMainWindow) -> None:
    show_data_manager_dialog(
        win.main_engine,
        win.event_engine,
        ensure_apps=lambda: ensure_data_manager_app(win.main_engine),
        parent=win,
    )


def open_notes_center_dialog(win: AshareMainWindow) -> None:
    show_notes_center_dialog(
        win.main_engine,
        win.event_engine,
        focus_watchlist=win.focus_watchlist_symbol,
        parent=win,
    )


def try_open_legacy_widget(win: AshareMainWindow, widget_class: type[QtWidgets.QWidget], name: str) -> bool:
    if name == "DataManager":
        open_data_manager_dialog(win)
        return True
    name_map = {
        "Ashare": "watchlist",
        "Home": "home",
        "CtaBacktester": "cta_backtest",
    }
    key = name_map.get(name)
    if key:
        nav_index = nav_index_for_key(win, key)
        if nav_index is not None:
            win._show_page(nav_index)
        else:
            show_page_by_key(win, key)
        return True
    return False
