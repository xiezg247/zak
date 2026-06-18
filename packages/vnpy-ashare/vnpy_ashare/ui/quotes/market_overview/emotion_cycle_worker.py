"""情绪周期后台加载 Worker。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot


class EmotionCycleLoadWorker(QtCore.QThread):
    finished = QtCore.Signal(object)

    def run(self) -> None:
        try:
            snapshot = load_emotion_cycle_snapshot(fetch_if_missing=True)
        except Exception:
            snapshot = None
        self.finished.emit(snapshot)
