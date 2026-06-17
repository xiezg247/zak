"""20cm 弹性维度：创/科小盘 + 涨幅。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.board import matches_board
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.base import DimensionHit
from vnpy_ashare.screener.hard_filters import apply_screening_filters, row_symbol
from vnpy_ashare.screener.sector.sector_summary import attach_industry

_CM20_MIN_CHANGE = 7.0
_CM20_SWEET_MV_YI = (20.0, 80.0)
_CM20_MAX_MV_YI = 150.0


def is_cm20_row(row: dict[str, Any]) -> bool:
    symbol = row_symbol(row)
    if not symbol:
        return False
    return matches_board(symbol, "创业板") or matches_board(symbol, "科创板")


def cm20_elastic_score(row: dict[str, Any], *, amount_rank: float = 0.5) -> float:
    change = float(row.get("change_pct") or 0)
    change_score = min(1.0, max(0.0, change / 20.0))
    mv_wan = float(row.get("total_mv") or row.get("circ_mv") or 0)
    mv_yi = mv_wan / 10_000.0 if mv_wan > 0 else 0.0
    if mv_yi <= 0:
        size_score = 0.5
    elif mv_yi < _CM20_SWEET_MV_YI[0]:
        size_score = 0.35
    elif mv_yi <= _CM20_SWEET_MV_YI[1]:
        size_score = 1.0
    elif mv_yi <= _CM20_MAX_MV_YI:
        size_score = 0.65
    else:
        size_score = 0.25
    raw = change_score * 0.55 + size_score * 0.30 + min(1.0, max(0.0, amount_rank)) * 0.15
    return round(max(0.0, min(100.0, raw * 100.0)), 1)


def _amount_rank_map(rows: list[dict[str, Any]]) -> dict[str, float]:
    amounts = [(str(row.get("vt_symbol") or ""), float(row.get("amount") or 0)) for row in rows]
    amounts = [(vt, amt) for vt, amt in amounts if vt]
    if not amounts:
        return {}
    sorted_amounts = sorted(amount for _, amount in amounts)
    n = len(sorted_amounts)
    result: dict[str, float] = {}
    for vt, amount in amounts:
        if amount <= 0:
            result[vt] = 0.0
            continue
        rank = sum(1 for value in sorted_amounts if value <= amount)
        result[vt] = rank / n
    return result


def run_cm20_elastic(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    enriched = attach_industry(snapshot.rows)
    if not enriched:
        return [], snapshot.total

    candidates: list[dict[str, Any]] = []
    for row in enriched:
        if not is_cm20_row(row):
            continue
        change = float(row.get("change_pct") or 0)
        if change < _CM20_MIN_CHANGE:
            continue
        item = dict(row)
        item["board_tag"] = "20cm"
        candidates.append(item)

    filtered = apply_screening_filters(candidates)
    if not filtered:
        return [], snapshot.total

    amount_ranks = _amount_rank_map(filtered)
    filtered.sort(
        key=lambda item: (
            cm20_elastic_score(item, amount_rank=amount_ranks.get(str(item.get("vt_symbol") or ""), 0.0)),
            float(item.get("change_pct") or 0),
        ),
        reverse=True,
    )
    top_rows = filtered[:pool_size]

    hits: list[DimensionHit] = []
    for row in top_rows:
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        amount_rank = amount_ranks.get(vt_symbol, 0.0)
        score = cm20_elastic_score(row, amount_rank=amount_rank)
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id="cm20_elastic",
                label="20cm",
                weight=weight,
                score=score,
                reason=_cm20_reason(row, score),
                row=row,
            )
        )
    return hits, snapshot.total


def _cm20_reason(row: dict[str, Any], score: float) -> str:
    symbol = row_symbol(row)
    board = "创" if symbol.startswith("300") else "科"
    change = float(row.get("change_pct") or 0)
    industry = str(row.get("industry") or "—")
    return f"20cm·{board}：{industry} 弹性 {score:.0f}，涨幅 {change:+.2f}%"
