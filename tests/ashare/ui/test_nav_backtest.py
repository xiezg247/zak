"""回测入口：侧栏移除、菜单栏弹窗。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401


def test_backtest_keys_not_in_sidebar() -> None:
    from vnpy_ashare.ui.shell.nav import APP_NAV_ENTRIES, BACKTEST_ENTRIES
    from vnpy_ashare.ui.shell.shortcuts import BACKTEST_SHORTCUTS

    sidebar_keys = {entry.key for entry in APP_NAV_ENTRIES}
    backtest_keys = {entry.key for entry in BACKTEST_ENTRIES}
    assert backtest_keys == {"cta_backtest", "batch_backtest"}
    assert backtest_keys.isdisjoint(sidebar_keys)
    assert BACKTEST_SHORTCUTS["cta_backtest"] == "Ctrl+Shift+8"
    assert BACKTEST_SHORTCUTS["batch_backtest"] == "Ctrl+Shift+9"


def test_show_page_by_key_skips_backtest_pages() -> None:
    from vnpy_ashare.ui.shell.main_window_pages import show_page_by_key

    win = MagicMock()
    win._current_key = "home"
    win._page_widgets = {}
    win.stack = MagicMock()
    win._floating_controller = None

    show_page_by_key(win, "cta_backtest")
    show_page_by_key(win, "batch_backtest")

    win.stack.addWidget.assert_not_called()
    win.stack.setCurrentWidget.assert_not_called()


def test_open_backtest_menu_dialog_routes_by_key() -> None:
    from vnpy_ashare.ui.shell.main_window_pages import open_backtest_menu_dialog

    win = MagicMock()
    with patch("vnpy_ashare.ui.shell.main_window_pages.open_backtest_dialog") as open_single:
        with patch("vnpy_ashare.ui.shell.main_window_pages.open_batch_backtest_dialog") as open_batch:
            open_backtest_menu_dialog(win, "cta_backtest")
            open_backtest_menu_dialog(win, "batch_backtest")

    open_single.assert_called_once_with(win)
    open_batch.assert_called_once_with(win)
