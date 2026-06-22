"""信号区 / 持仓区策略计算合并：同 config 的标的单次 batch。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from vnpy.trader.ui import QtCore

from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
from vnpy_ashare.ui.quotes._host_widget import as_qwidget
from vnpy_ashare.ui.quotes.watchlist_signals.worker import WatchlistSignalWorker
from vnpy_common.ui.qt_helpers import release_thread

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost

StrategyZone = Literal["signal", "position"]
SignalCache = dict[str, object]
OnComplete = Callable[[SignalCache], None]
OnFailed = Callable[[str], None]


@dataclass
class _BatchJob:
    zone: StrategyZone
    symbols: list[str]
    config: WatchlistSignalConfig
    on_complete: OnComplete
    on_failed: OnFailed


@dataclass
class _MergedBatch:
    config: WatchlistSignalConfig
    symbols: set[str] = field(default_factory=set)
    jobs: list[_BatchJob] = field(default_factory=list)


class WatchlistStrategyBatchCoordinator:
    """合并同策略参数的 signal / position 刷新请求，单次 worker 计算。"""

    def __init__(self, page: WatchlistHost) -> None:
        self._page = page
        self._worker: WatchlistSignalWorker | None = None
        self._pending_jobs: list[_BatchJob] = []
        self._queued_jobs: list[_BatchJob] = []
        self._flush_pending = False
        self._active_zones: set[StrategyZone] = set()

    def is_busy(self) -> bool:
        worker = self._worker
        return worker is not None and worker.isRunning()

    def is_refreshing_zone(self, zone: StrategyZone) -> bool:
        return zone in self._active_zones and self.is_busy()

    def submit(
        self,
        *,
        zone: StrategyZone,
        symbols: list[str],
        config: WatchlistSignalConfig,
        on_complete: OnComplete,
        on_failed: OnFailed,
    ) -> None:
        if not symbols:
            return
        self._pending_jobs.append(
            _BatchJob(
                zone=zone,
                symbols=list(symbols),
                config=config.normalized(),
                on_complete=on_complete,
                on_failed=on_failed,
            ),
        )
        self._schedule_flush()

    def stop(self) -> None:
        self._pending_jobs.clear()
        self._queued_jobs.clear()
        self._active_zones.clear()
        worker = self._worker
        if worker is not None:
            self._worker = None
            for signal in (worker.finished, worker.failed):
                try:
                    signal.disconnect()
                except (TypeError, RuntimeError):
                    pass
            release_thread(self._page._retired_workers, worker, timeout_ms=0)

    def _schedule_flush(self) -> None:
        if self._flush_pending:
            return
        self._flush_pending = True
        QtCore.QTimer.singleShot(0, self._flush)

    def _flush(self) -> None:
        self._flush_pending = False
        if not self._page._active:
            self._pending_jobs.clear()
            return
        if self.is_busy():
            self._queued_jobs.extend(self._pending_jobs)
            self._pending_jobs.clear()
            return

        jobs = self._pending_jobs
        self._pending_jobs.clear()
        if not jobs:
            return

        merged_groups = self._merge_jobs(jobs)
        if not merged_groups:
            return

        first, rest = merged_groups[0], merged_groups[1:]
        for group in rest:
            self._queued_jobs.extend(group.jobs)
        self._start_merged(first)

    def _merge_jobs(self, jobs: list[_BatchJob]) -> list[_MergedBatch]:
        grouped: dict[str, _MergedBatch] = {}
        for job in jobs:
            key = job.config.cache_key()
            merged = grouped.get(key)
            if merged is None:
                merged = _MergedBatch(config=job.config)
                grouped[key] = merged
            merged.symbols.update(job.symbols)
            merged.jobs.append(job)
        return list(grouped.values())

    def _start_merged(self, merged: _MergedBatch) -> None:
        service = self._page._get_analysis_service()
        if service is None:
            for job in merged.jobs:
                job.on_failed("analysis service unavailable")
            self._schedule_flush()
            return

        symbols = sorted(merged.symbols)
        config = merged.config
        self._active_zones = {job.zone for job in merged.jobs}

        worker = WatchlistSignalWorker(
            service,
            symbols=symbols,
            class_name=config.class_name,
            fast_window=config.fast_window,
            slow_window=config.slow_window,
            parent=as_qwidget(self._page),
        )
        self._worker = worker

        def on_finished(cache: SignalCache) -> None:
            if self._worker is worker:
                self._worker = None
            self._active_zones.clear()
            try:
                if not self._page._active:
                    return
                for job in merged.jobs:
                    subset = {vt: cache[vt] for vt in job.symbols if vt in cache}
                    job.on_complete(subset)
            finally:
                release_thread(self._page._retired_workers, worker, timeout_ms=0)
                self._drain_queued()

        def on_failed(msg: str) -> None:
            if self._worker is worker:
                self._worker = None
            self._active_zones.clear()
            try:
                for job in merged.jobs:
                    job.on_failed(msg)
            finally:
                release_thread(self._page._retired_workers, worker, timeout_ms=0)
                self._drain_queued()

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def _drain_queued(self) -> None:
        if not self._queued_jobs and not self._pending_jobs:
            return
        if self._queued_jobs:
            self._pending_jobs.extend(self._queued_jobs)
            self._queued_jobs.clear()
        self._schedule_flush()
