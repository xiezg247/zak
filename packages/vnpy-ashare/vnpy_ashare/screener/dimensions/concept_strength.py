"""概念板块维度：同花顺概念指数强势成分。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRow
from vnpy_ashare.integrations.tushare.concept_board import build_hot_concept_vt_symbol_map
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.base import DimensionHit, quote_hits
from vnpy_ashare.screener.preset.rules import _quote_row


def run_concept_strength(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    vt_to_concept, hot_names = build_hot_concept_vt_symbol_map()
    if not vt_to_concept:
        return [], snapshot.total

    candidates: list[QuoteRow] = []
    for row in snapshot.rows:
        vt_symbol = str(row.get("vt_symbol") or "")
        concept = vt_to_concept.get(vt_symbol)
        if not concept:
            continue
        base = _quote_row(row)
        base["concept_name"] = concept
        base["hot_concepts"] = hot_names[:5]
        candidates.append(base)

    candidates.sort(key=lambda item: float(item.get("change_pct") or 0), reverse=True)
    top_rows = candidates[:pool_size]

    return quote_hits(
        top_rows,
        dimension_id="concept_strength",
        label="概念",
        weight=weight,
        reason_builder=lambda row, rank: _concept_reason(row, rank),
    ), snapshot.total


def _concept_reason(row: dict[str, Any], rank: int) -> str:
    concept = str(row.get("concept_name") or "未知")
    change = float(row.get("change_pct") or 0)
    return f"概念：{concept} 强势，涨幅 {change:+.2f}%，排名第 {rank}"
