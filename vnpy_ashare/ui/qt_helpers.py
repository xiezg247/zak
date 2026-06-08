"""Qt 通用辅助（线程生命周期、窗口几何）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets


def retain_thread_until_finished(
    retired: list[QtCore.QThread],
    worker: QtCore.QThread,
) -> None:
    """保留 QThread 引用直至 run() 结束，避免 destroy-while-running。"""
    if worker in retired:
        return
    retired.append(worker)

    def _release(*_args: object) -> None:
        try:
            retired.remove(worker)
        except ValueError:
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
    timeout_ms: int = 500,
) -> None:
    """短暂等待线程结束；超时则转入 retired 列表直至自然结束。"""
    if worker is None:
        return
    try:
        if worker.isRunning():
            worker.wait(timeout_ms)
    except RuntimeError:
        return
    try:
        if worker.isRunning():
            retain_thread_until_finished(retired, worker)
    except RuntimeError:
        pass


def ensure_geometry_on_screen(widget: QtWidgets.QWidget) -> None:
    """确保窗口至少部分落在已连接屏幕的可用区域内。"""
    frame = widget.frameGeometry()
    if frame.isEmpty():
        return

    screens = QtGui.QGuiApplication.screens()
    if not screens:
        return

    def intersects_any_screen(rect: QtCore.QRect) -> bool:
        for screen in screens:
            if rect.intersects(screen.availableGeometry()):
                return True
        return False

    if intersects_any_screen(frame):
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
    if geometry is not None:
        widget.restoreGeometry(geometry)
    ensure_geometry_on_screen(widget)
