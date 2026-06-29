"""榜单过滤、排序与日内指标计算。"""

from __future__ import annotations

from typing import Literal

from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.quotes.rank.rank_catalog import RankDefinition, RankFilter

RankScope = Literal["all", "watchlist"]


def compute_intraday_change_pct(quote: QuoteSnapshot) -> float:
    """相对昨收的日内涨跌：(现价 - 今开) / 昨收 * 100。"""
    if quote.prev_close <= 0:
        return 0.0
    return (quote.last_price - quote.open_price) / quote.prev_close * 100.0


def quote_rank_value(quote: QuoteSnapshot, field: str) -> float:
    if field == "intraday_change_pct":
        return compute_intraday_change_pct(quote)
    try:
        return float(getattr(quote, field, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _value_passes_filter(value: float, spec_filter: RankFilter) -> bool:
    if spec_filter.min_value is not None:
        if spec_filter.min_inclusive:
            if value < spec_filter.min_value:
                return False
        elif value <= spec_filter.min_value:
            return False
    if spec_filter.max_value is not None:
        if spec_filter.max_inclusive:
            if value > spec_filter.max_value:
                return False
        elif value >= spec_filter.max_value:
            return False
    return True


def quote_matches_rank(quote: QuoteSnapshot, spec: RankDefinition) -> bool:
    if spec.filter is not None:
        value = quote_rank_value(quote, spec.filter.field)
        if not _value_passes_filter(value, spec.filter):
            return False
    if spec.require_open_below_prev:
        if quote.prev_close <= 0 or quote.open_price >= quote.prev_close:
            return False
    if spec.require_open_above_prev:
        if quote.prev_close <= 0 or quote.open_price <= quote.prev_close:
            return False
    if spec.require_intraday_rise and quote.last_price <= quote.open_price:
        return False
    if spec.require_intraday_fall and quote.last_price >= quote.open_price:
        return False
    return True


def rank_needs_post_process(spec: RankDefinition) -> bool:
    return spec.filter is not None or spec.require_open_below_prev or spec.require_open_above_prev or spec.require_intraday_rise or spec.require_intraday_fall


def should_finalize_rank_catalog(spec: RankDefinition) -> bool:
    return rank_needs_post_process(spec) or spec.scope != "all"


def finalize_rank_catalog(
    tf_symbols: list[str],
    quotes: dict[str, QuoteSnapshot],
    spec: RankDefinition,
) -> list[str]:
    """按榜定义过滤并排序 tickflow symbol 列表。"""
    from vnpy_ashare.quotes.rank.rank_engine_polars import finalize_rank_catalog_polars

    return finalize_rank_catalog_polars(tf_symbols, quotes, spec)
