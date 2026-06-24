"""macOS 下从终端启动 Qt GUI 时的进程与日志适配。"""

from __future__ import annotations

import ctypes
import os
import sys
import threading
from ctypes import Structure, byref, c_int, c_uint32
from typing import TextIO


class _ProcessSerialNumber(Structure):
    _fields_ = [("highLongOfPSN", c_uint32), ("lowLongOfPSN", c_uint32)]


_K_PROCESS_TRANSFORM_TO_FOREGROUND_APPLICATION = 1

# Apple 框架偶发写入 stderr 的已知无害噪音（终端 python 非 .app bundle 时常见）
_IMK_LOG_MARKERS = (
    "IMKCFRunLoopWakeUpReliable",
    "error messaging the mach port for IMK",
)
_TSM_LOG_MARKERS = (
    "TSMSendMessageToUIServer:",
    "com.apple.tsm.uiserver",
)

_stderr_filter_installed = False


def is_macos() -> bool:
    return sys.platform == "darwin"


def configure_macos_before_qt() -> None:
    """在首次 import Qt 之前调用（macOS 日志过滤等）。"""
    if not is_macos():
        return
    # 降低 os_log / IMK / CFRunLoop 等写入终端的调试输出
    os.environ.setdefault("OS_ACTIVITY_MODE", "disable")


def promote_macos_gui_process() -> bool:
    """将终端启动的 Python 进程注册为前台 GUI 应用，便于连接 TSM/输入法服务。"""
    if not is_macos():
        return False
    try:
        app_services = ctypes.CDLL("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
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


def is_benign_macos_gui_log(text: str) -> bool:
    """判断是否为可安全忽略的 macOS GUI 运行时 stderr 行。"""
    if all(marker in text for marker in _TSM_LOG_MARKERS):
        return True
    return any(marker in text for marker in _IMK_LOG_MARKERS)


class _MacOSGuiStderrFilter:
    """过滤 macOS 已知无害 stderr 噪音，保留其它日志。"""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    def write(self, data: str) -> int:
        if is_benign_macos_gui_log(data):
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


def _emit_filtered_stderr_line(line: bytes, writer: object) -> None:
    text = line.decode("utf-8", errors="replace")
    if is_benign_macos_gui_log(text):
        return
    write = getattr(writer, "write", None)
    if write is None:
        return
    write(line)
    flush = getattr(writer, "flush", None)
    if flush is not None:
        flush()


def _install_native_stderr_line_filter() -> None:
    """将 fd=2 重定向经行级过滤，捕获 IMK/TSM 等绕过 sys.stderr 的原生日志。"""
    try:
        read_fd, write_fd = os.pipe()
        saved_fd = os.dup(2)
    except OSError:
        return

    os.dup2(write_fd, 2)
    os.close(write_fd)

    def pump() -> None:
        buf = b""
        reader = os.fdopen(read_fd, "rb", closefd=True)
        writer = os.fdopen(saved_fd, "wb", closefd=False)
        try:
            while True:
                chunk = reader.read(8192)
                if not chunk:
                    break
                buf += chunk
                while True:
                    newline = buf.find(b"\n")
                    if newline < 0:
                        break
                    line = buf[: newline + 1]
                    buf = buf[newline + 1 :]
                    _emit_filtered_stderr_line(line, writer)
            if buf:
                _emit_filtered_stderr_line(buf, writer)
        finally:
            reader.close()
            writer.close()

    threading.Thread(target=pump, name="zak-macos-stderr", daemon=True).start()


def install_macos_gui_log_filter() -> None:
    """安装 stderr 过滤器，隐藏 TSM/IMK 等偶发 IPC 失败日志。"""
    global _stderr_filter_installed
    if not is_macos() or _stderr_filter_installed:
        return
    _stderr_filter_installed = True

    configure_macos_before_qt()
    _install_native_stderr_line_filter()

    stderr = sys.stderr
    if not isinstance(stderr, _MacOSGuiStderrFilter):
        sys.stderr = _MacOSGuiStderrFilter(stderr)


def bootstrap_macos_gui_runtime(*, before_qt: bool = False) -> None:
    """GUI 启动时统一调用：before_qt=True 在 import Qt 前，False 在 QApplication 创建后。"""
    if before_qt:
        install_macos_gui_log_filter()
        return
    promote_macos_gui_process()
