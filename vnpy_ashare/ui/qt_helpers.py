"""Qt 通用辅助（线程生命周期、窗口几何）。"""

from __future__ import annotations

import warnings

from vnpy.trader.ui import QtCore, QtGui, QtWidgets


def thread_is_active(worker: QtCore.QThread | None) -> bool:
    """QThread 是否仍在运行（已销毁的 worker 视为未运行）。"""
    if worker is None:
        return False
    try:
        return worker.isRunning()
    except RuntimeError:
        return False


def disconnect_worker_auto_delete(worker: QtCore.QThread) -> None:
    """断开 finished/failed → deleteLater，避免 deactivate 与自动销毁竞态。"""
    for signal_name in ("finished", "failed"):
        signal = getattr(worker, signal_name, None)
        if signal is None:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            try:
                signal.disconnect(worker.deleteLater)
            except (TypeError, RuntimeError):
                pass


def retain_thread_until_finished(
    retired: list[QtCore.QThread],
    worker: QtCore.QThread,
) -> None:
    """保留 QThread 引用直至 run() 结束，避免 destroy-while-running。"""
    if worker in retired:
        return
    try:
        worker.setParent(None)
    except RuntimeError:
        return
    retired.append(worker)

    def _release(*_args: object) -> None:
        try:
            retired.remove(worker)
        except ValueError:
            pass
        try:
            worker.deleteLater()
        except RuntimeError:
            pass

    for signal_name in ("finished", "failed"):
        signal = getattr(worker, signal_name, None)
        if signal is None:
            continue
        try:
            signal.connect(_release)
        except (RuntimeError, TypeError):
            pass


def release_thread(
    retired: list[QtCore.QThread],
    worker: QtCore.QThread | None,
    *,
    timeout_ms: int = 3000,
) -> None:
    """短暂等待线程结束；超时则转入 retired 列表直至自然结束。"""
    if worker is None:
        return
    disconnect_worker_auto_delete(worker)
    try:
        worker.setParent(None)
    except RuntimeError:
        return
    try:
        if worker.isRunning():
            worker.wait(timeout_ms)
    except RuntimeError:
        return
    try:
        if worker.isRunning():
            retain_thread_until_finished(retired, worker)
            return
        worker.deleteLater()
    except RuntimeError:
        pass


def frame_intersects_any_screen(rect: QtCore.QRect) -> bool:
    screens = QtGui.QGuiApplication.screens()
    if not screens or rect.isEmpty():
        return False
    for screen in screens:
        if rect.intersects(screen.availableGeometry()):
            return True
    return False


def ensure_geometry_on_screen(widget: QtWidgets.QWidget) -> None:
    """确保窗口至少部分落在已连接屏幕的可用区域内。"""
    frame = widget.frameGeometry()
    if frame.isEmpty():
        return

    screens = QtGui.QGuiApplication.screens()
    if not screens:
        return

    if frame_intersects_any_screen(frame):
        return

    target = QtGui.QGuiApplication.primaryScreen() or screens[0]
    avail = target.availableGeometry()
    width = min(max(frame.width(), widget.minimumWidth()), avail.width())
    height = min(max(frame.height(), widget.minimumHeight()), avail.height())
    x = avail.x() + max(0, (avail.width() - width) // 2)
    y = avail.y() + max(0, (avail.height() - height) // 2)
    widget.setGeometry(x, y, width, height)


def restore_geometry_on_screen(
    widget: QtWidgets.QWidget,
    geometry: QtCore.QByteArray | object | None,
) -> None:
    """恢复保存的几何信息，并校正到可见屏幕内。"""
    if isinstance(geometry, QtCore.QByteArray) and not geometry.isEmpty():
        widget.restoreGeometry(geometry)
        if not frame_intersects_any_screen(widget.frameGeometry()):
            widget.hide()
            ensure_geometry_on_screen(widget)
    else:
        ensure_geometry_on_screen(widget)


def clamp_point_in_parent(
    parent: QtWidgets.QWidget,
    widget: QtWidgets.QWidget,
    point: QtCore.QPoint,
) -> QtCore.QPoint:
    """将子控件坐标限制在父控件范围内。"""
    max_x = max(0, parent.width() - widget.width())
    max_y = max(0, parent.height() - widget.height())
    return QtCore.QPoint(
        min(max(0, point.x()), max_x),
        min(max(0, point.y()), max_y),
    )


def restore_child_position(
    parent: QtWidgets.QWidget,
    widget: QtWidgets.QWidget,
    pos: object | None,
    *,
    default_x: int | None = None,
    default_y: int | None = None,
) -> None:
    """恢复子控件在父控件内的位置。"""
    if default_x is None:
        default_x = max(0, parent.width() - widget.width() - 20)
    if default_y is None:
        default_y = max(0, parent.height() - widget.height() - 20)
    if isinstance(pos, QtCore.QPoint):
        point = clamp_point_in_parent(parent, widget, pos)
    else:
        point = clamp_point_in_parent(
            parent,
            widget,
            QtCore.QPoint(default_x, default_y),
        )
    widget.move(point)
