"""带 TTL 的进程内内存缓存（monotonic 计时）。"""

from __future__ import annotations

import time
from typing import Generic, TypeVar

T = TypeVar("T")


class TtlCache(Generic[T]):
    def __init__(self) -> None:
        self._value: T | None = None
        self._cached_at: float = 0.0

    def peek(self, *, max_age_sec: float) -> T | None:
        if self._value is None:
            return None
        if time.monotonic() - self._cached_at > max_age_sec:
            return None
        return self._value

    def store(self, value: T | None) -> None:
        if value is None:
            self.invalidate()
            return
        self._value = value
        self._cached_at = time.monotonic()

    def invalidate(self) -> None:
        self._value = None
        self._cached_at = 0.0
