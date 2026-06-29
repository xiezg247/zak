"""zak GUI QApplication 启动（跳过 vnpy 默认 qdarkstyle）。"""

from __future__ import annotations

import ctypes
import platform
import sys
import threading
import traceback
import types

import vnpy.trader.ui.qt as vnpy_qt
from loguru import logger
from vnpy.trader.setting import SETTINGS
from vnpy.trader.ui import QtGui, QtWidgets
from vnpy.trader.ui.qt import ExceptionWidget
from vnpy.trader.utility import get_icon_path


def create_zak_qapp(app_name: str = "zak") -> QtWidgets.QApplication:
    """创建 QApplication：不加载 qdarkstyle，全局 QSS 由 ThemeManager 接管。"""
    qapp = QtWidgets.QApplication(sys.argv)
    qapp.setStyleSheet("")

    font = QtGui.QFont(SETTINGS["font.family"], SETTINGS["font.size"])
    qapp.setFont(font)

    icon = QtGui.QIcon(get_icon_path(vnpy_qt.__file__, "vnpy.ico"))
    qapp.setWindowIcon(icon)

    if "Windows" in platform.uname():
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_name)  # type: ignore[attr-defined]

    exception_widget = ExceptionWidget()

    def excepthook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: types.TracebackType | None,
    ) -> None:
        logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical("Main thread exception")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        exception_widget.signal.emit(msg)

    sys.excepthook = excepthook

    def threading_excepthook(args: threading.ExceptHookArgs) -> None:
        if args.exc_value and args.exc_traceback:
            logger.opt(exception=(args.exc_type, args.exc_value, args.exc_traceback)).critical("Background thread exception")
            sys.__excepthook__(args.exc_type, args.exc_value, args.exc_traceback)
        msg = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        exception_widget.signal.emit(msg)

    threading.excepthook = threading_excepthook

    return qapp
