"""自选雷达：候选标的行情补全。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRowLike
from vnpy_ashare.quotes.radar.radar_quotes import merge_row_quotes, quotes_for_vt_symbols

__all__ = [
    "has_quote_data",
    "quotes_for_candidates",
]


def quotes_for_candidates(candidates: list[str]) -> dict[str, dict[str, Any]]:
    """自选 vt_symbol → 行情行（委托统一按需查找实现）。"""
    return quotes_for_vt_symbols(candidates)


def has_quote_data(row: QuoteRowLike) -> bool:
    merged = merge_row_quotes(row)
    return bool(
        merged.get("change_pct") not in (None, "")
        or float(merged.get("last_price") or merged.get("close") or 0) > 0
        or float(merged.get("amount") or 0) > 0
    )
