"""延迟空闲任务：用户交互期间推迟预热。"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock, patch

import pytest
from vnpy.trader.ui import QtWidgets

import tests._bootstrap  # noqa: F401


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_is_user_idle_when_recent_activity(qapp: QtWidgets.QApplication) -> None:
    from vnpy.trader.ui import QtCore

    from vnpy_ashare.ui.shell.deferred_idle import is_user_idle, touch_user_activity

    class _Win:
        pass

    win = _Win()
    with patch.object(qapp, "applicationState", return_value=QtCore.Qt.ApplicationState.ApplicationActive):
        touch_user_activity(win)
        assert is_user_idle(win, idle_ms=3000) is False


def test_run_when_idle_waits_for_min_delay(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.ui.shell.deferred_idle import run_when_idle

    win = MagicMock()
    win._last_user_activity_at = 0.0
    calls: list[int] = []
    timers: list[tuple[int, object]] = []

    def _single_shot(ms: int, callback) -> None:
        timers.append((ms, callback))

    t = 1000.0
    with patch("vnpy_ashare.ui.shell.deferred_idle.time.monotonic", side_effect=[t, t]):
        with patch(
            "vnpy_ashare.ui.shell.deferred_idle.QtCore.QTimer.singleShot",
            side_effect=_single_shot,
        ):
            with patch("vnpy_ashare.ui.shell.deferred_idle.is_user_idle", return_value=True):
                run_when_idle(win, lambda: calls.append(1), not_before_ms=2000, scheduled_at=t)

    assert calls == []
    assert len(timers) == 1
    assert timers[0][0] == 2000


def test_run_when_idle_retries_while_busy(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.ui.shell.deferred_idle import run_when_idle

    win = MagicMock()
    calls: list[int] = []
    timers: list[tuple[int, object]] = []

    def _single_shot(ms: int, callback) -> None:
        timers.append((ms, callback))

    t = 1000.0
    with patch("vnpy_ashare.ui.shell.deferred_idle.time.monotonic", side_effect=[t + 5, t + 5]):
        with patch(
            "vnpy_ashare.ui.shell.deferred_idle.QtCore.QTimer.singleShot",
            side_effect=_single_shot,
        ):
            with patch("vnpy_ashare.ui.shell.deferred_idle.is_user_idle", return_value=False):
                run_when_idle(win, lambda: calls.append(1), not_before_ms=0, retry_ms=500, scheduled_at=t)

    assert calls == []
    assert len(timers) == 1
    assert timers[0][0] == 500


def test_run_when_idle_executes_when_ready(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.ui.shell.deferred_idle import run_when_idle

    win = MagicMock()
    calls: list[int] = []
    t = 1000.0

    with patch("vnpy_ashare.ui.shell.deferred_idle.time.monotonic", side_effect=[t + 3, t + 3]):
        with patch("vnpy_ashare.ui.shell.deferred_idle.is_user_idle", return_value=True):
            run_when_idle(win, lambda: calls.append(1), not_before_ms=2000, scheduled_at=t)

    assert calls == [1]


def test_watchlist_prewarm_skips_if_page_exists(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.ui.shell.main_window_scheduler import schedule_deferred_watchlist_prewarm

    win = MagicMock()
    win._watchlist_prewarm_scheduled = False
    win._page_widgets = {"watchlist": MagicMock()}

    with patch("vnpy_ashare.ui.shell.main_window_scheduler.run_when_idle") as run_idle:
        schedule_deferred_watchlist_prewarm(win)
        callback = run_idle.call_args.args[1]
        with patch("vnpy_ashare.ui.shell.main_window_pages.get_or_create_page") as create_page:
            callback()
            create_page.assert_not_called()

    assert win._watchlist_prewarm_scheduled is True
