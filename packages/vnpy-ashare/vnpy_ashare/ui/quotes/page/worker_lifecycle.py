"""QuotesPage Worker 取消与释放。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtCore

from vnpy_common.ui.qt_helpers import release_thread

_CANCEL_WORKER_ATTRS = (
    "_load_worker",
    "_market_worker",
    "_prefetch_worker",
    "_sync_worker",
    "_download_worker",
    "_batch_fill_worker",
    "_batch_gap_fill_worker",
)

_RELEASE_WORKER_ATTRS = (
    "_load_worker",
    "_market_worker",
    "_prefetch_worker",
    "_sync_worker",
    "_bars_worker",
    "_download_worker",
    "_batch_fill_worker",
    "_batch_gap_fill_worker",
    "_gap_worker",
    "_quotes_worker",
    "_depth_worker",
    "_diagnose_worker",
    "_invalid_bar_cleanup_worker",
)


def wait_worker_release(page: Any, attr: str, *, timeout_ms: int = 3000) -> None:
    worker = getattr(page, attr, None)
    if worker is None:
        return
    setattr(page, attr, None)
    release_thread(page._retired_workers, worker, timeout_ms=timeout_ms)


def release_worker(page: Any, worker: QtCore.QThread | None) -> None:
    release_thread(page._retired_workers, worker, timeout_ms=0)


def cancel_quotes_page_workers(page: Any) -> None:
    for attr in _CANCEL_WORKER_ATTRS:
        worker = getattr(page, attr, None)
        if worker is not None and hasattr(worker, "request_cancel"):
            worker.request_cancel()


def release_quotes_page_workers(page: Any, *, timeout_ms: int = 0) -> None:
    for attr in _RELEASE_WORKER_ATTRS:
        wait_worker_release(page, attr, timeout_ms=timeout_ms)
    page._batch_backtest.release_workers(page._retired_workers)


def teardown_quotes_page_workers(page: Any) -> None:
    """页面 deactivate 时取消并释放后台 Worker。"""
    cancel_quotes_page_workers(page)
    page._task_guard.end()
    page._set_busy(False, lock_table=page._task_lock_table)
    release_quotes_page_workers(page, timeout_ms=0)
