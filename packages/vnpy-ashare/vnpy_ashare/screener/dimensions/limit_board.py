"""连板涨停维度：limit_times + 涨停池。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.base import DimensionHit


def run_limit_board(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.engine.dimensions.limit_board import run_limit_board_polars

    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    return run_limit_board_polars(
        list(snapshot.rows),
        pool_size=pool_size,
        weight=weight,
        total=snapshot.total,
    )


def _limit_board_reason(row: dict[str, Any], rank: int) -> str:
    boards = int(float(row.get("limit_times") or 1))
    industry = str(row.get("industry") or "—")
    change = float(row.get("change_pct") or 0)
    board_text = f"{boards}板" if boards >= 2 else "首板"
    return f"连板：{industry} {board_text}，涨幅 {change:+.2f}%，排名第 {rank}"
