"""自选页侧栏切换：先切页再异步 activate。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401


def test_show_page_by_key_watchlist_defers_activate() -> None:
    from vnpy_ashare.ui.shell.main_window_pages import show_page_by_key

    win = MagicMock()
    win._current_key = "home"
    win._page_widgets = {"home": MagicMock(), "watchlist": MagicMock()}
    win.stack.indexOf.return_value = 0
    win._floating_controller = None

    watchlist_widget = win._page_widgets["watchlist"]
    watchlist_widget.page = MagicMock()

    timers: list[object] = []

    def _capture_timer(_ms: int, callback) -> None:
        timers.append(callback)

    with patch("vnpy_ashare.ui.shell.main_window_pages.QtCore.QTimer.singleShot", side_effect=_capture_timer):
        show_page_by_key(win, "watchlist", nav_index=1)

    win.stack.setCurrentWidget.assert_called_once_with(watchlist_widget)
    win.sidebar.set_active_index.assert_called_once_with(1)
    watchlist_widget.page.begin_tab_switch_loading.assert_called_once()
    watchlist_widget.activate.assert_not_called()
    win._page_widgets["home"].deactivate.assert_not_called()

    assert len(timers) == 1
    timers[0]()

    win._page_widgets["home"].deactivate.assert_called_once()
    watchlist_widget.activate.assert_called_once()
    assert win._current_key == "watchlist"
