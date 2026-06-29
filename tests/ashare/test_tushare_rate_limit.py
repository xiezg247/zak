"""Tushare 频率限制测试。"""

from __future__ import annotations

import threading
import time
import unittest

from vnpy_ashare.integrations.tushare.rate_limit import (
    SlidingWindowLimiter,
    acquire_tushare,
    is_rate_limited,
    is_transient_network_error,
)


class SlidingWindowLimiterTests(unittest.TestCase):
    def test_blocks_when_window_full(self) -> None:
        limiter = SlidingWindowLimiter(2, period_sec=0.4)
        limiter.acquire()
        limiter.acquire()
        start = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.15)

    def test_thread_safe_acquire(self) -> None:
        limiter = SlidingWindowLimiter(30, period_sec=1.0)
        counter = {"value": 0}

        def worker() -> None:
            for _ in range(10):
                limiter.acquire()
                counter["value"] += 1

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual(counter["value"], 30)


class RateLimitHelperTests(unittest.TestCase):
    def test_detects_rate_limit_message(self) -> None:
        self.assertTrue(is_rate_limited(Exception("抱歉，您访问接口(daily)频率超限(500次/分钟)")))

    def test_acquire_daily_does_not_raise(self) -> None:
        acquire_tushare("daily")


if __name__ == "__main__":
    unittest.main()
