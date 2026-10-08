"""雷达 Worker 生命周期：启动接线、取消、释放（统一 card / group / prefetch）。"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TypeVar

from vnpy.trader.ui import QtCore

from vnpy_ashare.quotes.radar.loaders import RadarCardData
from vnpy_ashare.ui.quotes.radar.worker import RadarCardLoadWorker, RadarGroupLoadWorker
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active

TWorker = TypeVar("TWorker", bound=QtCore.QThread)

CardFinished = Callable[[str, RadarCardData, bool, RadarCardLoadWorker], None]
CardFailed = Callable[[str, str], None]
GroupFinished = Callable[[dict[str, RadarCardData], dict[str, str], RadarGroupLoadWorker], None]
GroupFailed = Callable[[str], None]
PrefetchFinished = Callable[[dict[str, RadarCardData], dict[str, str], RadarGroupLoadWorker], None]


class RadarWorkerHost:
    """持有雷达三类 Worker 与 retired 列表。"""

    def __init__(self) -> None:
        self._card_workers: dict[str, RadarCardLoadWorker] = {}
        self._group: RadarGroupLoadWorker | None = None
        self._prefetch: RadarGroupLoadWorker | None = None
        self._retired: list[QtCore.QThread] = []

    @property
    def group(self) -> RadarGroupLoadWorker | None:
        return self._group

    @group.setter
    def group(self, worker: RadarGroupLoadWorker | None) -> None:
        """测试与兼容用：直接挂当前分组 Worker。"""
        self._group = worker

    @property
    def prefetch(self) -> RadarGroupLoadWorker | None:
        return self._prefetch

    def card_is_active(self, card_id: str) -> bool:
        return thread_is_active(self._card_workers.get(card_id))

    def group_is_active(self) -> bool:
        return thread_is_active(self._group)

    def prefetch_is_active(self) -> bool:
        return thread_is_active(self._prefetch)

    def group_covers_card(self, card_id: str) -> bool:
        worker = self._group
        return bool(worker is not None and thread_is_active(worker) and card_id in worker.card_ids)

    def is_current_card(self, card_id: str, worker: RadarCardLoadWorker | None) -> bool:
        if worker is None:
            return True
        return self._card_workers.get(card_id) is worker

    def is_current_group(self, worker: RadarGroupLoadWorker) -> bool:
        return self._group is worker

    def is_current_prefetch(self, worker: RadarGroupLoadWorker) -> bool:
        return self._prefetch is worker

    def active_load_count(self) -> int:
        active = sum(1 for worker in self._card_workers.values() if thread_is_active(worker))
        if self.group_is_active():
            active += 1
        return active

    def start_card(
        self,
        worker: RadarCardLoadWorker,
        *,
        on_finished: CardFinished,
        on_failed: CardFailed,
    ) -> None:
        card_id = worker.card_id
        self.cancel_card(card_id)
        self._card_workers[card_id] = worker

        def _finished(cid: str, data: object, quote_only: bool, w: RadarCardLoadWorker = worker) -> None:
            on_finished(cid, data, quote_only, w)  # type: ignore[arg-type]
            self.release_card(w)

        def _failed(cid: str, message: str, w: RadarCardLoadWorker = worker) -> None:
            on_failed(cid, message)
            self.release_card(w)

        worker.finished.connect(_finished)
        worker.failed.connect(_failed)
        worker.start()

    def start_group(
        self,
        worker: RadarGroupLoadWorker,
        *,
        on_finished: GroupFinished,
        on_failed: GroupFailed,
        cancel_card_ids: Iterable[str] | None = None,
    ) -> None:
        self.cancel_group()
        for card_id in cancel_card_ids or worker.card_ids:
            self.cancel_card(card_id)
        self._group = worker

        def _finished(loaded: object, errors: object, w: RadarGroupLoadWorker = worker) -> None:
            on_finished(loaded, errors, w)  # type: ignore[arg-type]
            self.release_group(w)

        def _failed(message: str, w: RadarGroupLoadWorker = worker) -> None:
            on_failed(message)
            self.release_group(w)

        worker.finished.connect(_finished)
        worker.failed.connect(_failed)
        worker.start()

    def start_prefetch(
        self,
        worker: RadarGroupLoadWorker,
        *,
        on_finished: PrefetchFinished,
    ) -> None:
        self.cancel_prefetch()
        self._prefetch = worker

        def _finished(loaded: object, errors: object, w: RadarGroupLoadWorker = worker) -> None:
            on_finished(loaded, errors, w)  # type: ignore[arg-type]
            self.release_prefetch(w)

        def _failed(_message: str, w: RadarGroupLoadWorker = worker) -> None:
            self.release_prefetch(w)

        worker.finished.connect(_finished)
        worker.failed.connect(_failed)
        worker.start()

    def cancel_card(self, card_id: str) -> None:
        worker = self._card_workers.pop(card_id, None)
        if worker is None:
            return
        worker.request_cancel()
        release_thread(self._retired, worker, timeout_ms=0)

    def cancel_group(self) -> None:
        worker = self._group
        if worker is None:
            return
        self._group = None
        worker.request_cancel()
        release_thread(self._retired, worker, timeout_ms=0)

    def cancel_prefetch(self) -> None:
        worker = self._prefetch
        if worker is None:
            return
        self._prefetch = None
        worker.request_cancel()
        release_thread(self._retired, worker, timeout_ms=0)

    def cancel_all(self) -> None:
        self.cancel_group()
        self.cancel_prefetch()
        for card_id in list(self._card_workers):
            self.cancel_card(card_id)

    def release_card(self, worker: RadarCardLoadWorker) -> None:
        card_id = worker.card_id
        if self._card_workers.get(card_id) is worker:
            self._card_workers.pop(card_id, None)
        release_thread(self._retired, worker)

    def release_group(self, worker: RadarGroupLoadWorker) -> None:
        if self._group is worker:
            self._group = None
        release_thread(self._retired, worker)

    def release_prefetch(self, worker: RadarGroupLoadWorker) -> None:
        if self._prefetch is worker:
            self._prefetch = None
        release_thread(self._retired, worker)
