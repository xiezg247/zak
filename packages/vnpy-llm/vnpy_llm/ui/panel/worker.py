"""后台流式对话线程。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_llm.app.engine import LlmEngine
from vnpy_llm.chat.client import StreamCancelled


class ChatWorker(QtCore.QThread):
    finished_ok = QtCore.Signal()
    cancelled = QtCore.Signal()
    failed = QtCore.Signal(str)

    def __init__(self, engine: LlmEngine, user_text: str, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._user_text = user_text

    def run(self) -> None:
        try:
            for _ in self._engine.stream_reply(self._user_text):
                if self.isInterruptionRequested():
                    self._engine.request_cancel_stream()
                    return
            if not self.isInterruptionRequested():
                self.finished_ok.emit()
        except StreamCancelled:
            self.cancelled.emit()
        except Exception as ex:
            if not self.isInterruptionRequested():
                self.failed.emit(str(ex))

    def safe_stop(self, *, polite_wait_ms: int = 10000, force_wait_ms: int = 3000) -> None:
        """等待线程结束；超时则强制终止。"""
        if not self.isRunning():
            return
        self._engine.request_cancel_stream()
        self.requestInterruption()
        if self.wait(polite_wait_ms):
            return
        self.terminate()
        self.wait(force_wait_ms)
