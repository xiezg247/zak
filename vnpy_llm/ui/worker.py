"""后台流式对话线程。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_llm.engine import LlmEngine


class ChatWorker(QtCore.QThread):
    finished_ok = QtCore.Signal()
    failed = QtCore.Signal(str)

    def __init__(self, engine: LlmEngine, user_text: str, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._user_text = user_text

    def run(self) -> None:
        try:
            for _ in self._engine.stream_reply(self._user_text):
                pass
            self.finished_ok.emit()
        except Exception as ex:
            self.failed.emit(str(ex))
