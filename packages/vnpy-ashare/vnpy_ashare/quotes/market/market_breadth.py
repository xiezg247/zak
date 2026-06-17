"""全市场广度统计（涨跌家数、涨跌停近似、成交额合计）。"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from vnpy_ashare.domain.market.breadth import (
    LIMIT_DOWN_PCT,
    LIMIT_UP_PCT,
    LimitSource,
    MarketBreadthSnapshot,
)
from vnpy_ashare.domain.market.quote_row import QuoteRowLike
from vnpy_ashare.integrations.tushare.factors import fetch_limit_list_d

__all__ = [
    "LIMIT_DOWN_PCT",
    "LIMIT_UP_PCT",
    "LimitSource",
    "MarketBreadthSnapshot",
    "compute_market_breadth",
    "merge_official_limit_counts",
]

def _coerce_change_pct(row: QuoteRowLike) -> float | None:
    raw = row.get("change_pct")
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(value):
        return None
    return value


def _coerce_amount(row: QuoteRowLike) -> float:
    raw = row.get("amount")
    if raw is None:
        return 0.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(value) or value < 0:
        return 0.0
    return value


def compute_market_breadth(
    rows: Sequence[QuoteRowLike],
    *,
    updated_at: str | None = None,
) -> MarketBreadthSnapshot:
    """从全市场行情行聚合市场广度。"""
    up = down = flat = 0
    limit_up = limit_down = 0
    total_amount = 0.0
    sample_size = 0

    for row in rows:
        change_pct = _coerce_change_pct(row)
        if change_pct is None:
            continue
        sample_size += 1
        total_amount += _coerce_amount(row)
        if change_pct > 0:
            up += 1
        elif change_pct < 0:
            down += 1
        else:
            flat += 1
        if change_pct >= LIMIT_UP_PCT:
            limit_up += 1
        elif change_pct <= LIMIT_DOWN_PCT:
            limit_down += 1

    return MarketBreadthSnapshot(
        up=up,
        down=down,
        flat=flat,
        limit_up=limit_up,
        limit_down=limit_down,
        total_amount=total_amount,
        sample_size=sample_size,
        updated_at=updated_at,
    )


def count_limit_from_rows(limit_rows: list[dict[str, Any]]) -> tuple[int, int]:
    """从 Tushare limit_list_d 行统计涨跌停家数。"""
    limit_up = sum(1 for row in limit_rows if str(row.get("limit") or "") == "U")
    limit_down = sum(1 for row in limit_rows if str(row.get("limit") or "") == "D")
    return limit_up, limit_down


def merge_official_limit_counts(breadth: MarketBreadthSnapshot) -> MarketBreadthSnapshot:
    """若 Tushare 涨跌停列表可用，覆盖近似涨跌停计数。"""
    try:
        limit_rows, _trade_date = fetch_limit_list_d()
    except Exception:
        return breadth
    if not limit_rows:
        return breadth
    limit_up, limit_down = count_limit_from_rows(limit_rows)
    return breadth.model_copy(
        update={"limit_up": limit_up, "limit_down": limit_down, "limit_source": "tushare"},
    )
