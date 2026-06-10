"""K 线下载任务有限并发（TickFlow / datafeed 拉取）。"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")

DEFAULT_DOWNLOAD_MAX_WORKERS = 3
_RETRY_DELAY_SEC = 0.5
_MAX_ATTEMPTS = 2


def download_max_workers(*, item_count: int) -> int:
    """并发下载 worker 数（DOWNLOAD_MAX_WORKERS，默认 3，上限 6）。"""
    raw = os.getenv("DOWNLOAD_MAX_WORKERS", str(DEFAULT_DOWNLOAD_MAX_WORKERS)).strip()
    try:
        configured = int(raw)
    except ValueError:
        configured = DEFAULT_DOWNLOAD_MAX_WORKERS
    configured = max(1, min(configured, 6))
    return min(configured, item_count)


def _is_retryable(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "locked" in message or "timeout" in message or "429" in message or "rate" in message


def run_with_retry(func: Callable[[], R]) -> R:
    """遇 SQLite 锁 / 限流时短暂退避重试。"""
    last_exc: BaseException | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return func()
        except BaseException as ex:
            last_exc = ex
            if attempt + 1 >= _MAX_ATTEMPTS or not _is_retryable(ex):
                raise
            time.sleep(_RETRY_DELAY_SEC * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def run_parallel_map(
    items: list[T],
    worker: Callable[[T], R],
    *,
    max_workers: int | None = None,
    on_complete: Callable[[int, T, R], None] | None = None,
) -> list[R]:
    """并行执行 worker，返回与 items 同序的结果列表。"""
    if not items:
        return []

    workers = max_workers if max_workers is not None else download_max_workers(item_count=len(items))
    if workers <= 1 or len(items) <= 1:
        results: list[R] = []
        for index, item in enumerate(items):
            result = run_with_retry(lambda item=item: worker(item))
            results.append(result)
            if on_complete is not None:
                on_complete(index, item, result)
        return results

    ordered: list[R | None] = [None] * len(items)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {
            pool.submit(run_with_retry, lambda item=item: worker(item)): (index, item)
            for index, item in enumerate(items)
        }
        for future in as_completed(future_map):
            index, item = future_map[future]
            result = future.result()
            ordered[index] = result
            if on_complete is not None:
                on_complete(index, item, result)
    if any(value is None for value in ordered):
        raise RuntimeError("parallel map missing results")
    return ordered  # type: ignore[return-value]
