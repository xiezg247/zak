"""换手维度：相对换手率排行。"""

from __future__ import annotations

from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.base import DimensionHit
def run_turnover(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.engine.dimensions.turnover import run_turnover_polars

    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    return run_turnover_polars(
        list(snapshot.rows),
        pool_size=pool_size,
        weight=weight,
        total=snapshot.total,
    )
