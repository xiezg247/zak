"""主窗口延迟任务：用户空闲后再执行，避免与交互争抢主线程。"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from vnpy.trader.ui import QtCore, QtWidgets

if TYPE_CHECKING:
    from vnpy_ashare.ui.shell.main_window import AshareMainWindow

IDLE_PREWARM_MS = 3000
IDLE_RETRY_MS = 1000
MOUSE_MOVE_THROTTLE_SEC = 0.5

_ACTIVITY_EVENTS = frozenset(
    {
        QtCore.QEvent.Type.MouseButtonPress,
        QtCore.QEvent.Type.MouseButtonDblClick,
        QtCore.QEvent.Type.KeyPress,
        QtCore.QEvent.Type.Wheel,
        QtCore.QEvent.Type.TouchBegin,
    }
)


def touch_user_activity(win: Any) -> None:
    win._last_user_activity_at = time.monotonic()


def bind_idle_activity_tracking(win: AshareMainWindow) -> None:
    if getattr(win, "_idle_activity_bound", False):
        return
    win._idle_activity_bound = True
    touch_user_activity(win)

    class _ActivityFilter(QtCore.QObject):
        def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: ARG002
            event_type = event.type()
            if event_type in _ACTIVITY_EVENTS:
                touch_user_activity(win)
                return False
            if event_type == QtCore.QEvent.Type.MouseMove:
                now = time.monotonic()
                last_move = getattr(win, "_last_mouse_move_at", 0.0)
                if now - last_move >= MOUSE_MOVE_THROTTLE_SEC:
                    win._last_mouse_move_at = now
                    touch_user_activity(win)
            return False

    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    win._idle_activity_filter = _ActivityFilter(win)
    app.installEventFilter(win._idle_activity_filter)


def is_user_idle(win: Any, idle_ms: int = IDLE_PREWARM_MS) -> bool:
    app = QtWidgets.QApplication.instance()
    if app is not None and app.applicationState() != QtCore.Qt.ApplicationState.ApplicationActive:
        return True
    last = getattr(win, "_last_user_activity_at", None)
    if last is None:
        return True
    return (time.monotonic() - last) * 1000 >= idle_ms


def run_when_idle(
    win: Any,
    callback: Callable[[], None],
    *,
    not_before_ms: int = 0,
    idle_ms: int = IDLE_PREWARM_MS,
    retry_ms: int = IDLE_RETRY_MS,
    scheduled_at: float | None = None,
) -> None:
    """满足最小延迟且用户空闲后再执行；忙碌则周期性重试。"""
    started_at = scheduled_at if scheduled_at is not None else time.monotonic()

    def _attempt() -> None:
        elapsed_ms = (time.monotonic() - started_at) * 1000
        if elapsed_ms < not_before_ms:
            QtCore.QTimer.singleShot(
                max(int(not_before_ms - elapsed_ms), 1),
                _attempt,
            )
            return
        if not is_user_idle(win, idle_ms):
            QtCore.QTimer.singleShot(retry_ms, _attempt)
            return
        callback()

    _attempt()
