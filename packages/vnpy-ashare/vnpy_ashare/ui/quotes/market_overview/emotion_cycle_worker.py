"""情绪周期后台加载 Worker。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore


class EmotionCycleLoadWorker(QtCore.QThread):
    finished = QtCore.Signal(object)

    def run(self) -> None:
        from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot

        self.finished.emit(load_emotion_cycle_snapshot(fetch_if_missing=True))
