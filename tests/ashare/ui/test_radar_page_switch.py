"""雷达页侧栏切换：先切页再异步 activate。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401


def _run_deferred_switch(*, nav_index: int = 5) -> tuple[MagicMock, list]:
    from vnpy_ashare.ui.shell.main_window_pages import show_page_by_key

    win = MagicMock()
    win._current_key = "home"
    win._page_widgets = {"home": MagicMock(), "radar": MagicMock()}
    win.stack.indexOf.return_value = 0
    win._floating_controller = None

    widget = win._page_widgets["radar"]
    widget.page = MagicMock()

    timers: list[object] = []

    def _capture_timer(_ms: int, callback) -> None:
        timers.append(callback)

    with patch("vnpy_ashare.ui.shell.main_window_pages.QtCore.QTimer.singleShot", side_effect=_capture_timer):
        show_page_by_key(win, "radar", nav_index=nav_index)

    return win, timers


def test_show_page_by_key_radar_defers_activate() -> None:
    win, timers = _run_deferred_switch(nav_index=5)
    radar_widget = win._page_widgets["radar"]

    win.stack.setCurrentWidget.assert_called_once_with(radar_widget)
    win.sidebar.set_active_index.assert_called_once_with(5)
    radar_widget.page.begin_tab_switch_loading.assert_called_once()
    radar_widget.activate.assert_not_called()
    win._page_widgets["home"].deactivate.assert_not_called()

    assert len(timers) == 1
    timers[0]()

    win._page_widgets["home"].deactivate.assert_called_once()
    radar_widget.activate.assert_called_once()
    assert win._current_key == "radar"


def test_show_page_by_key_radar_defers_first_create() -> None:
    from vnpy_ashare.ui.shell.main_window_pages import show_page_by_key

    win = MagicMock()
    win._current_key = "home"
    win._page_widgets = {"home": MagicMock()}
    win._floating_controller = None

    radar_widget = MagicMock()
    radar_widget.page = MagicMock()
    timers: list[object] = []

    def _capture_timer(_ms: int, callback) -> None:
        timers.append(callback)

    with patch("vnpy_ashare.ui.shell.main_window_pages.QtCore.QTimer.singleShot", side_effect=_capture_timer):
        with patch(
            "vnpy_ashare.ui.shell.main_window_pages.get_or_create_page",
            return_value=radar_widget,
        ) as create_page:
            with patch("vnpy_ashare.ui.shell.main_window_pages._switch_page_deferred") as deferred_switch:
                show_page_by_key(win, "radar", nav_index=5)
                assert len(timers) == 1
                timers[0]()

    win.sidebar.set_active_index.assert_called_once_with(5)
    win.stack.setCurrentWidget.assert_not_called()
    create_page.assert_called_once_with(win, "radar")
    deferred_switch.assert_called_once()
