"""维度执行共用类型与工具。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DimensionHit:
    """单维度命中记录。"""

    vt_symbol: str
    dimension_id: str
    label: str
    weight: float
    score: float
    reason: str
    row: dict[str, Any]


def rank_score(rank: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(max(0.0, (total - rank + 1) / total * 100), 1)


def quote_hits(
    rows: list[dict[str, Any]],
    *,
    dimension_id: str,
    label: str,
    weight: float,
    reason_builder,
) -> list[DimensionHit]:
    hits: list[DimensionHit] = []
    for index, row in enumerate(rows, start=1):
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id=dimension_id,
                label=label,
                weight=weight,
                score=rank_score(index, len(rows)),
                reason=reason_builder(row, index),
                row=dict(row),
            )
        )
    return hits


def merge_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for row in rows:
        for key, value in row.items():
            if key in merged and merged[key] not in (None, "", 0):
                continue
            if value not in (None, ""):
                merged[key] = value
    return merged


def fundamental_base_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": row.get("symbol", ""),
        "name": row.get("name", ""),
        "vt_symbol": row.get("vt_symbol", ""),
        "close": row.get("close", 0),
        "pe_ttm": row.get("pe_ttm", 0),
        "pct_chg": row.get("pct_chg", row.get("change_pct", 0)),
        "turnover_rate": row.get("turnover_rate", 0),
        "volume_ratio": row.get("volume_ratio", 0),
        "source": row.get("source", "tushare"),
    }
