"""市场摘要内存缓存（连板梯队等，供 UI 只读、避免主线程重算）。"""

from __future__ import annotations

import time
from typing import Any

_CACHE_TTL_SEC = 300.0
_ladder_counts: dict[str, int] | None = None
_ladder_cached_at: float = 0.0


def store_limit_ladder_counts(counts: dict[str, int] | None) -> None:
    global _ladder_counts, _ladder_cached_at
    _ladder_counts = dict(counts) if counts else None
    _ladder_cached_at = time.monotonic()


def peek_limit_ladder_counts(*, max_age_sec: float = _CACHE_TTL_SEC) -> dict[str, int] | None:
    if _ladder_counts is None:
        return None
    if time.monotonic() - _ladder_cached_at > max_age_sec:
        return None
    return dict(_ladder_counts)


def invalidate_limit_ladder_cache() -> None:
    global _ladder_counts, _ladder_cached_at
    _ladder_counts = None
    _ladder_cached_at = 0.0


def resolve_limit_ladder_counts(
    rows: list[dict[str, Any]],
    *,
    compute: Any,
) -> dict[str, int]:
    """优先读预热缓存，缺失时再全量计算。"""
    cached = peek_limit_ladder_counts()
    if cached is not None:
        return cached
    counts: dict[str, int] = compute(rows)
    return counts
