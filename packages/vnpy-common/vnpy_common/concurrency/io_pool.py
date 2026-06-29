"""进程级共享 I/O 线程池（避免频繁创建/销毁 ThreadPoolExecutor）。"""

from __future__ import annotations

import atexit
import os
import threading
from concurrent.futures import ThreadPoolExecutor

_DEFAULT_MAX_WORKERS = 8
_CAP_MAX_WORKERS = 16

_lock = threading.Lock()
_executor: ThreadPoolExecutor | None = None


def global_io_max_workers() -> int:
    raw = os.getenv("ZAK_GLOBAL_IO_MAX_WORKERS", str(_DEFAULT_MAX_WORKERS)).strip()
    try:
        configured = int(raw)
    except ValueError:
        configured = _DEFAULT_MAX_WORKERS
    return max(1, min(configured, _CAP_MAX_WORKERS))


def get_io_executor() -> ThreadPoolExecutor:
    """返回进程内单例 I/O 线程池（zak-io-* 线程）。"""
    global _executor
    with _lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=global_io_max_workers(),
                thread_name_prefix="zak-io",
            )
        return _executor


def shutdown_io_executor() -> None:
    global _executor
    with _lock:
        if _executor is not None:
            _executor.shutdown(wait=False, cancel_futures=True)
            _executor = None


atexit.register(shutdown_io_executor)
