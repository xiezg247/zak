"""首板人气维度：limit_times=1 + 封板时间代理。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.base import DimensionHit
from vnpy_ashare.trading.signals.seal_time import format_seal_time_label


def run_first_board(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.engine.dimensions.first_board import run_first_board_polars

    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    return run_first_board_polars(
        list(snapshot.rows),
        pool_size=pool_size,
        weight=weight,
        total=snapshot.total,
    )


def _first_board_reason(row: dict[str, Any], seal_label: str) -> str:
    industry = str(row.get("industry") or "—")
    change = float(row.get("change_pct") or 0)
    seal = seal_label or format_seal_time_label(str(row.get("first_time") or "")) or "封板时间待补"
    score = float(row.get("first_board_score") or 0)
    strength_raw = row.get("seal_strength_score")
    strength_hint = ""
    if strength_raw not in (None, ""):
        try:
            strength_hint = f"，封单强度 {float(str(strength_raw)) * 100:.0f}"
        except (TypeError, ValueError):
            strength_hint = ""
    reopen_label = str(row.get("seal_reopen_label") or "").strip()
    reopen_hint = f"，{reopen_label}" if reopen_label else ""
    return f"首板：{industry} {seal}{strength_hint}{reopen_hint}，人气 {score:.0f}，涨幅 {change:+.2f}%"
