"""动量维度：涨幅排行。"""

from __future__ import annotations

from vnpy_ashare.screener.data.data_source import fetch_fundamental_screening_rows, load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.base import DimensionHit, fundamental_base_row, quote_hits, rank_score
from vnpy_ashare.screener.preset.presets import SCREENER_CHANGE_TOP
from vnpy_ashare.screener.preset.rules import apply_quote_preset


def run_momentum(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    try:
        snapshot = load_screening_quote_snapshot()
        rows = apply_quote_preset(SCREENER_CHANGE_TOP, snapshot.rows, top_n=pool_size)
        return quote_hits(
            rows,
            dimension_id="momentum",
            label="动量",
            weight=weight,
            reason_builder=lambda row, rank: f"动量：涨幅 {float(row.get('change_pct') or 0):+.2f}%，排名第 {rank}",
        ), snapshot.total
    except MarketQuotesLoadError:
        raw_rows, _trade_date, _ = fetch_fundamental_screening_rows()
        if not raw_rows:
            return [], 0
        sorted_rows = sorted(
            raw_rows,
            key=lambda item: float(item.get("pct_chg") or item.get("change_pct") or 0),
            reverse=True,
        )[:pool_size]
        hits: list[DimensionHit] = []
        for index, row in enumerate(sorted_rows, start=1):
            vt_symbol = str(row.get("vt_symbol") or "")
            if not vt_symbol:
                continue
            pct = float(row.get("pct_chg") or row.get("change_pct") or 0)
            hits.append(
                DimensionHit(
                    vt_symbol=vt_symbol,
                    dimension_id="momentum",
                    label="动量",
                    weight=weight,
                    score=rank_score(index, len(sorted_rows)),
                    reason=f"动量：日涨幅 {pct:+.2f}%，排名第 {index}",
                    row=fundamental_base_row(row),
                )
            )
        return hits, len(raw_rows)
