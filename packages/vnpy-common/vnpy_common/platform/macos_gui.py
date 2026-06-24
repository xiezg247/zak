"""macOS 下从终端启动 Qt GUI 时的进程与日志适配。"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import Structure, byref, c_int, c_uint32
from typing import TextIO


class _ProcessSerialNumber(Structure):
    _fields_ = [("highLongOfPSN", c_uint32), ("lowLongOfPSN", c_uint32)]


_K_PROCESS_TRANSFORM_TO_FOREGROUND_APPLICATION = 1

# Apple 框架偶发写入 stderr 的已知无害 TSM 噪音（终端 python 非 .app  bundle 时常见）
_TSM_LOG_MARKERS = (
    "TSMSendMessageToUIServer:",
    "com.apple.tsm.uiserver",
)


def is_macos() -> bool:
    return sys.platform == "darwin"


def configure_macos_before_qt() -> None:
    """在首次 import Qt 之前调用，降低 Cocoa 初始化差异。"""
    if not is_macos():
        return
    os.environ.setdefault("QT_MAC_WANTS_LAYER", "1")


def promote_macos_gui_process() -> bool:
    """将终端启动的 Python 进程注册为前台 GUI 应用，便于连接 TSM/输入法服务。"""
    if not is_macos():
        return False
    try:
        app_services = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
    except OSError:
        return False

    psn = _ProcessSerialNumber()
    get_current = getattr(app_services, "GetCurrentProcess", None)
    if get_current is not None:
        get_current.argtypes = [ctypes.POINTER(_ProcessSerialNumber)]
        get_current.restype = c_int
        if get_current(byref(psn)) != 0:
            return False
    else:
        psn = _ProcessSerialNumber(0, 2)

    transform = app_services.TransformProcessType
    transform.argtypes = [ctypes.POINTER(_ProcessSerialNumber), c_uint32]
    transform.restype = c_int
    status = transform(byref(psn), _K_PROCESS_TRANSFORM_TO_FOREGROUND_APPLICATION)
    return bool(status == 0)


def _is_benign_tsm_log(text: str) -> bool:
    return all(marker in text for marker in _TSM_LOG_MARKERS)


class _MacOSGuiStderrFilter:
    """过滤 macOS TSM 已知无害 stderr 噪音，保留其它日志。"""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    def write(self, data: str) -> int:
        if _is_benign_tsm_log(data):
            return len(data)
        return self._stream.write(data)

    def flush(self) -> None:
        self._stream.flush()

    def fileno(self) -> int:
        return self._stream.fileno()

    def isatty(self) -> bool:
        return self._stream.isatty()

    def __getattr__(self, name: str) -> object:
        return getattr(self._stream, name)


def install_macos_gui_log_filter() -> None:
    """安装 stderr 过滤器，隐藏 TSM uiserver 偶发 IPC 失败日志。"""
    if not is_macos():
        return
    stderr = sys.stderr
    if isinstance(stderr, _MacOSGuiStderrFilter):
        return
    sys.stderr = _MacOSGuiStderrFilter(stderr)


def bootstrap_macos_gui_runtime(*, before_qt: bool = False) -> None:
    """GUI 启动时统一调用：before_qt=True 在 import Qt 前，False 在 QApplication 创建后。"""
    if before_qt:
        configure_macos_before_qt()
        install_macos_gui_log_filter()
        return
    promote_macos_gui_process()
