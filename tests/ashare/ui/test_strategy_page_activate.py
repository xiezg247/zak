"""策略页 activate：同步路径仅标记 active，重活延后到下一帧。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401


def test_strategy_activate_defers_bootstrap_and_refresh() -> None:
    from vnpy_ashare.ui.quotes.page.session_lifecycle import activate_quotes_page

    page = MagicMock()
    page.page_name = "策略监控"
    page._watchlist_bootstrap = MagicMock()
    page.config.use_radar_cards = False
    page.config.show_watchlist_signals = True
    page.config.show_watchlist_positions = True

    timers: list[object] = []

    def _capture_timer(_ms: int, callback) -> None:
        timers.append(callback)

    with patch(
        "vnpy_ashare.ui.quotes.page.session_lifecycle._deferred_strategy_monitor_activate_frame1",
    ) as frame1:
        with patch("vnpy_ashare.ui.quotes.page.session_lifecycle.QtCore.QTimer.singleShot", side_effect=_capture_timer):
            activate_quotes_page(page)

        assert page._active is True
        page._watchlist_bootstrap.on_activate.assert_not_called()
        page._strategy_refresh.start.assert_not_called()
        page._signals.on_page_activated.assert_not_called()
        assert len(timers) == 1
        timers[0]()
        frame1.assert_called_once_with(page)


def test_strategy_activate_frame1_ends_tab_loading() -> None:
    from vnpy_ashare.ui.quotes.page.session_lifecycle import _deferred_strategy_monitor_activate_frame1

    page = MagicMock()
    page.page_name = "策略监控"
    page._active = True
    page._watchlist_bootstrap = MagicMock()

    with patch("vnpy_ashare.ui.quotes.page.session_lifecycle.QtCore.QTimer.singleShot") as shot:
        _deferred_strategy_monitor_activate_frame1(page)

    page.end_tab_switch_loading.assert_called_once()
    shot.assert_called_once()
