"""刷新情绪周期芯片（市场 / 雷达 / 自选共用）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot, peek_emotion_cycle_snapshot
from vnpy_ashare.ui.quotes.market_overview.emotion_cycle_worker import EmotionCycleLoadWorker
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.market_overview.emotion_cycle_chip import EmotionCycleChip

_active_worker: QtCore.QThread | None = None
_retired_workers: list[QtCore.QThread] = []


def refresh_emotion_cycle_chip(chip: EmotionCycleChip) -> None:
    """优先用缓存；无缓存则显示 loading 并在后台拉取，不阻塞 UI 启动。"""

    peeked = peek_emotion_cycle_snapshot()
    if peeked is not None:
        chip.apply_snapshot(peeked)
        return

    snapshot = load_emotion_cycle_snapshot(fetch_if_missing=False)
    if snapshot is not None:
        chip.apply_snapshot(snapshot)
        return

    chip.set_loading()
    _start_background_load(chip)


def _start_background_load(chip: EmotionCycleChip) -> None:
    global _active_worker
    if thread_is_active(_active_worker):
        return


    worker = EmotionCycleLoadWorker()
    _active_worker = worker

    def on_finished(snapshot: object) -> None:
        global _active_worker
        if _active_worker is worker:
            _active_worker = None
        release_thread(_retired_workers, worker)
        chip.apply_snapshot(snapshot)  # type: ignore[arg-type]

    worker.finished.connect(on_finished)
    worker.start()
