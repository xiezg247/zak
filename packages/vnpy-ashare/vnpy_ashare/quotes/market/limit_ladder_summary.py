"""市场页连板梯队汇总（复用雷达 D-01 逻辑）。"""

from __future__ import annotations

from collections.abc import Sequence

from vnpy_ashare.domain.market.quote_row import QuoteRow
from vnpy_ashare.quotes.core.enrich import get_cached_limit_times_map
from vnpy_ashare.quotes.radar.radar_limit_ladder import (
    build_limit_ladder_candidates,
    count_ladder_buckets,
)


def compute_limit_ladder_counts(rows: Sequence[QuoteRow]) -> dict[str, int]:
    """按 5板+ / 4板 / … / 首板 统计涨停池数量。"""
    if not rows:
        return count_ladder_buckets([])
    limit_map = get_cached_limit_times_map()
    candidates = build_limit_ladder_candidates(rows, limit_times_map=limit_map)
    return count_ladder_buckets(candidates)
