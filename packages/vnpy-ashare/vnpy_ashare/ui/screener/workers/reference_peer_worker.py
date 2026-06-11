"""参考选股（找同类）Worker。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.screener.reference.reference_peer import ReferencePeerCancelled, run_reference_peer_screen


class ReferencePeerWorker(QtCore.QThread):
    progress = QtCore.Signal(str)
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        vt_symbol: str,
        *,
        reference_name: str = "",
        top_n: int = 20,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.vt_symbol = vt_symbol
        self.reference_name = reference_name
        self.top_n = top_n

    def run(self) -> None:
        try:
            if self.isInterruptionRequested():
                return
            result = run_reference_peer_screen(
                self.vt_symbol,
                reference_name=self.reference_name,
                top_n=self.top_n,
                on_progress=self.progress.emit,
                cancelled=self.isInterruptionRequested,
            )
            if self.isInterruptionRequested():
                return
            self.finished.emit(result)
        except ReferencePeerCancelled:
            return
        except Exception as ex:
            if self.isInterruptionRequested():
                return
            self.failed.emit(str(ex))
