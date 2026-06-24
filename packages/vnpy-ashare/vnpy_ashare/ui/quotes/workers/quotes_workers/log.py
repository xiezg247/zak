"""Worker 日志 Signal 辅助。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore


def emit_worker_log(signal: QtCore.SignalInstance, message: object) -> None:
    text = str(message).strip()
    if text:
        signal.emit(text)
