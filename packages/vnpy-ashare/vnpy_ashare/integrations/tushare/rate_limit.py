"""Tushare Pro 接口频率限制（进程内全局、线程安全）。"""

from __future__ import annotations

import os
import threading
import time
from collections import deque

# Tushare daily 默认 500 次/分钟；留余量避免边界触发
_DEFAULT_LIMITS: dict[str, int] = {
    "daily": 450,
    "stk_mins": 400,
}
_PERIOD_SEC = 60.0
_RATE_LIMIT_MARKERS = ("频率超限", "429", "too many", "rate limit")


class SlidingWindowLimiter:
    """滑动窗口：任意 period 秒内最多 max_calls 次。"""

    def __init__(self, max_calls: int, *, period_sec: float = _PERIOD_SEC) -> None:
        self.max_calls = max(1, int(max_calls))
        self.period_sec = max(0.1, float(period_sec))
        self._lock = threading.Lock()
        self._timestamps: deque[float] = deque()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._timestamps and now - self._timestamps[0] >= self.period_sec:
                    self._timestamps.popleft()
                if len(self._timestamps) < self.max_calls:
                    self._timestamps.append(now)
                    return
                wait = self.period_sec - (now - self._timestamps[0])
            time.sleep(max(wait, 0.02))


_limiters: dict[str, SlidingWindowLimiter] = {}
_limiters_lock = threading.Lock()


def _env_limit(api_name: str, default: int) -> int:
    env_key = f"TUSHARE_{api_name.upper()}_MAX_PER_MIN"
    raw = os.getenv(env_key, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default
    return max(1, value)


def get_tushare_limiter(api_name: str) -> SlidingWindowLimiter:
    default = _DEFAULT_LIMITS.get(api_name, 400)
    max_calls = _env_limit(api_name, default)
    with _limiters_lock:
        limiter = _limiters.get(api_name)
        if limiter is None or limiter.max_calls != max_calls:
            limiter = SlidingWindowLimiter(max_calls)
            _limiters[api_name] = limiter
        return limiter


def acquire_tushare(api_name: str) -> None:
    """在调用 Tushare 接口前阻塞，直到未超出频率上限。"""
    get_tushare_limiter(api_name).acquire()


def is_rate_limited(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(marker.lower() in message for marker in _RATE_LIMIT_MARKERS)


def rate_limit_retry_delay(attempt: int) -> float:
    """限流后退避：首次短等，之后等满一个窗口。"""
    if attempt <= 0:
        return 2.0
    return _PERIOD_SEC + 2.0
