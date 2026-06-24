"""自选信号区批量计算 Worker。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from vnpy.trader.ui import QtCore

if TYPE_CHECKING:
    from vnpy.trader.engine import MainEngine

    from vnpy_ashare.services.analysis import AnalysisService


@dataclass
class WatchlistSignalWorkerPayload:
    """Worker 计算结果（信号 + 可选延续快照）。"""

    signals: dict[str, Any] = field(default_factory=dict)
    continuations: dict[str, Any] = field(default_factory=dict)


def unwrap_worker_payload(raw: object) -> WatchlistSignalWorkerPayload:
    if isinstance(raw, WatchlistSignalWorkerPayload):
        return raw
    raise TypeError(f"expected WatchlistSignalWorkerPayload, got {type(raw)!r}")


class WatchlistSignalWorker(QtCore.QThread):
    """批量计算信号区策略信号（含相对指数 enrich，延续可选）。"""

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
        include_continuation: bool = False,
        main_engine: MainEngine | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.analysis_service = analysis_service
        self.symbols = list(symbols)
        self.class_name = class_name
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.include_continuation = include_continuation
        self.main_engine = main_engine

    def run(self) -> None:
        try:
            cache = self.analysis_service.batch_strategy_signals(
                self.symbols,
                class_name=self.class_name,
                fast_window=self.fast_window,
                slow_window=self.slow_window,
                max_workers=1,
            )
            if cache:
                try:
                    cache = self.analysis_service.enrich_relative_index_batch(cache)
                except Exception:
                    pass
            continuations: dict[str, Any] = {}
            if self.include_continuation and cache:
                try:
                    continuations = self.analysis_service.enrich_continuation_batch(
                        list(cache),
                        cache,
                        main_engine=self.main_engine,
                    )
                except Exception:
                    continuations = {}
            self.finished.emit(
                WatchlistSignalWorkerPayload(signals=cache, continuations=continuations),
            )
        except Exception as ex:
            self.failed.emit(str(ex))
