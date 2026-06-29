"""共享 I/O 线程池测试。"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import tests._bootstrap  # noqa: F401
from vnpy_common.concurrency import io_pool


def test_global_io_max_workers_respects_env() -> None:
    prev = os.environ.get("ZAK_GLOBAL_IO_MAX_WORKERS")
    os.environ["ZAK_GLOBAL_IO_MAX_WORKERS"] = "4"
    try:
        assert io_pool.global_io_max_workers() == 4
    finally:
        if prev is None:
            os.environ.pop("ZAK_GLOBAL_IO_MAX_WORKERS", None)
        else:
            os.environ["ZAK_GLOBAL_IO_MAX_WORKERS"] = prev


def test_get_io_executor_is_singleton() -> None:
    io_pool.shutdown_io_executor()
    try:
        first = io_pool.get_io_executor()
        second = io_pool.get_io_executor()
        assert first is second
        assert isinstance(first, ThreadPoolExecutor)
    finally:
        io_pool.shutdown_io_executor()


def test_run_parallel_map_uses_shared_pool() -> None:
    from vnpy_ashare.data.download_concurrency import run_parallel_map

    io_pool.shutdown_io_executor()
    pool = io_pool.get_io_executor()
    try:
        with patch("vnpy_ashare.data.download_concurrency.get_io_executor", return_value=pool):
            values = run_parallel_map([1, 2, 3], lambda item: item * 2, max_workers=2)
        assert values == [2, 4, 6]
    finally:
        io_pool.shutdown_io_executor()
