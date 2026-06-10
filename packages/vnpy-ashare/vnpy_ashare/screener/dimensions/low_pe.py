"""估值维度：低 PE 排行。"""

from __future__ import annotations

from vnpy_ashare.screener.data_source import fetch_fundamental_screening_rows
from vnpy_ashare.screener.dimensions.base import DimensionHit, rank_score
from vnpy_ashare.screener.rules import apply_low_pe


def run_low_pe(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    raw_rows, _trade_date, _ = fetch_fundamental_screening_rows()
    if not raw_rows:
        return [], 0
    rows = apply_low_pe(raw_rows, top_n=pool_size)
    hits: list[DimensionHit] = []
    for index, row in enumerate(rows, start=1):
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        pe = float(row.get("pe_ttm") or 0)
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id="low_pe",
                label="估值",
                weight=weight,
                score=rank_score(index, len(rows)),
                reason=f"估值：PE(TTM) {pe:.2f}，排名第 {index}",
                row=dict(row),
            )
        )
    return hits, len(raw_rows)
