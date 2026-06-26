"""20cm 弹性维度：创/科小盘 + 涨幅。"""

from __future__ import annotations

from vnpy_ashare.domain.market.board import matches_board
from vnpy_ashare.domain.market.quote_row import QuoteRowLike
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.base import DimensionHit
from vnpy_ashare.screener.hard_filters import row_symbol


def is_cm20_row(row: QuoteRowLike) -> bool:
    symbol = row_symbol(row)
    if not symbol:
        return False
    return matches_board(symbol, "创业板") or matches_board(symbol, "科创板")


def cm20_elastic_score(row: QuoteRowLike, *, amount_rank: float = 0.5) -> float:
    change = float(row.get("change_pct") or 0)
    change_score = min(1.0, max(0.0, change / 20.0))
    mv_wan = float(row.get("total_mv") or row.get("circ_mv") or 0)
    mv_yi = mv_wan / 10_000.0 if mv_wan > 0 else 0.0
    if mv_yi <= 0:
        size_score = 0.5
    elif mv_yi < 20.0:
        size_score = 0.35
    elif mv_yi <= 80.0:
        size_score = 1.0
    elif mv_yi <= 150.0:
        size_score = 0.65
    else:
        size_score = 0.25
    raw = change_score * 0.55 + size_score * 0.30 + min(1.0, max(0.0, amount_rank)) * 0.15
    return round(max(0.0, min(100.0, raw * 100.0)), 1)


def run_cm20_elastic(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.engine.dimensions.cm20_elastic import run_cm20_elastic_polars

    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    return run_cm20_elastic_polars(
        list(snapshot.rows),
        pool_size=pool_size,
        weight=weight,
        total=snapshot.total,
    )


def _cm20_reason(row: QuoteRowLike, score: float) -> str:
    symbol = row_symbol(row)
    board = "创" if symbol.startswith("300") else "科"
    change = float(row.get("change_pct") or 0)
    industry = str(row.get("industry") or "—")
    return f"20cm·{board}：{industry} 弹性 {score:.0f}，涨幅 {change:+.2f}%"
