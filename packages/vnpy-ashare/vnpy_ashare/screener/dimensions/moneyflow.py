"""资金维度：主力净流入排行。"""

from __future__ import annotations

from vnpy_ashare.screener.data.data_source import fetch_moneyflow_with_fallback
from vnpy_ashare.screener.dimensions.base import DimensionHit, rank_score
from vnpy_ashare.screener.preset.rules import apply_moneyflow_in


def run_moneyflow(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    raw_rows, _trade_date = fetch_moneyflow_with_fallback()
    if not raw_rows:
        return [], 0
    rows = apply_moneyflow_in(raw_rows, top_n=pool_size)
    hits: list[DimensionHit] = []
    for index, row in enumerate(rows, start=1):
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        amount = float(row.get("net_mf_amount") or 0)
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id="moneyflow",
                label="资金",
                weight=weight,
                score=rank_score(index, len(rows)),
                reason=f"资金：主力净流入 {amount:,.0f} 万，排名第 {index}",
                row=dict(row),
            )
        )
    return hits, len(raw_rows)
