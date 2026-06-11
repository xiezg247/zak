"""雷达页后台加载 Worker。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.quotes.radar_loaders import load_radar_board


class RadarBoardLoadWorker(QtCore.QThread):
    finished = QtCore.Signal(dict)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        *,
        screen_task_variant: str,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._screen_task_variant = screen_task_variant
        self._cancelled = False

    def request_cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        if self._cancelled:
            return
        try:
            payload = load_radar_board(screen_task_variant=self._screen_task_variant)
        except Exception as ex:
            self.failed.emit(str(ex))
            return
        if self._cancelled:
            return
        self.finished.emit(payload)
