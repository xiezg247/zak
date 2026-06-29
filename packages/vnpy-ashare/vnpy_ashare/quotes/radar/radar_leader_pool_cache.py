"""龙头候选池会话级缓存（同 variant + pool_size 在 TTL 内复用）。"""

from __future__ import annotations

import time
from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRow

_POOL_TTL_SEC = 90.0
_pool_cache: dict[tuple[str, int], tuple[float, list[QuoteRow | dict[str, Any]], int]] = {}


def peek_leader_candidate_pool(
    *,
    variant: str,
    pool_size: int,
    max_age_sec: float = _POOL_TTL_SEC,
) -> tuple[list[QuoteRow | dict[str, Any]], int] | None:
    key = (variant, pool_size)
    entry = _pool_cache.get(key)
    if entry is None:
        return None
    cached_at, candidates, total = entry
    if time.monotonic() - cached_at > max_age_sec:
        _pool_cache.pop(key, None)
        return None
    return list(candidates), total


def store_leader_candidate_pool(
    *,
    variant: str,
    pool_size: int,
    candidates: list[QuoteRow | dict[str, Any]],
    total: int,
) -> None:
    _pool_cache[(variant, pool_size)] = (time.monotonic(), list(candidates), total)


def invalidate_leader_candidate_pool() -> None:
    _pool_cache.clear()
