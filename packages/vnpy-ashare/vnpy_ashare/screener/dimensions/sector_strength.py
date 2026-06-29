"""板块维度：强势行业成分股加分。"""

from __future__ import annotations

from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.base import DimensionHit


def run_sector_strength(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.engine.dimensions.sector_strength import run_sector_strength_polars

    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    return run_sector_strength_polars(
        list(snapshot.rows),
        pool_size=pool_size,
        weight=weight,
        total=snapshot.total,
    )


def _sector_reason(row: dict, rank: int) -> str:
    industry = str(row.get("industry") or "未知")
    change = float(row.get("change_pct") or 0)
    advance = row.get("industry_advance_pct")
    advance_note = f"，上涨占比 {float(advance):.0f}%" if advance is not None else ""
    return f"板块：{industry} 强势{advance_note}，涨幅 {change:+.2f}%，排名第 {rank}"
