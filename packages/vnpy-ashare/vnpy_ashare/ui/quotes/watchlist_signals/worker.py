"""自选信号区批量计算 Worker。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

if TYPE_CHECKING:
    from vnpy_ashare.services.analysis import AnalysisService


class WatchlistSignalWorker(QtCore.QThread):
    """批量计算信号区策略信号。"""

    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        analysis_service: AnalysisService,
        *,
        symbols: list[str],
        class_name: str = "AshareDoubleMaStrategy",
        fast_window: int = 10,
        slow_window: int = 20,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.analysis_service = analysis_service
        self.symbols = list(symbols)
        self.class_name = class_name
        self.fast_window = fast_window
        self.slow_window = slow_window

    def run(self) -> None:
        try:
            cache = self.analysis_service.batch_strategy_signals(
                self.symbols,
                class_name=self.class_name,
                fast_window=self.fast_window,
                slow_window=self.slow_window,
            )
            self.finished.emit(cache)
        except Exception as ex:
            self.failed.emit(str(ex))
