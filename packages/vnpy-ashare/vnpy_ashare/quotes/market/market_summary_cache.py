"""市场摘要内存缓存（连板梯队等，供 UI 只读、避免主线程重算）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.quotes.core.cache_ttl import TtlCache

_CACHE_TTL_SEC = 300.0
_ladder_cache: TtlCache[dict[str, int]] = TtlCache()


def store_limit_ladder_counts(counts: dict[str, int] | None) -> None:
    _ladder_cache.store(dict(counts) if counts else None)


def peek_limit_ladder_counts(*, max_age_sec: float = _CACHE_TTL_SEC) -> dict[str, int] | None:
    cached = _ladder_cache.peek(max_age_sec=max_age_sec)
    if cached is None:
        return None
    return dict(cached)


def invalidate_limit_ladder_cache() -> None:
    _ladder_cache.invalidate()


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
