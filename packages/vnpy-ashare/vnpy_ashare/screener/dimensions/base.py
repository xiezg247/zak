"""维度执行共用类型与工具。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import Field

from vnpy_ashare.domain.base import MutableModel
from vnpy_ashare.domain.market.quote_row import QuoteRowLike
from vnpy_ashare.screener.dimensions.scoring import blended_score, rank_score


class DimensionHit(MutableModel):
    """单维度命中记录。"""

    vt_symbol: str = Field(description="标的 vt_symbol")
    dimension_id: str = Field(description="维度标识")
    label: str = Field(description="维度展示名")
    weight: float = Field(description="维度权重")
    score: float = Field(description="维度得分")
    reason: str = Field(description="命中原因")
    row: dict[str, Any] = Field(description="原始行情行")


def quote_hits(
    rows: Sequence[QuoteRowLike],
    *,
    dimension_id: str,
    label: str,
    weight: float,
    reason_builder,
    metric_key: str | None = None,
    score_adjustment: Any | None = None,
) -> list[DimensionHit]:
    hits: list[DimensionHit] = []
    metric_values: list[float] = []
    if metric_key:
        metric_values = [float(row.get(metric_key) or 0) for row in rows]
    for index, row in enumerate(rows, start=1):
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        if metric_key:
            score = blended_score(
                index,
                len(rows),
                float(row.get(metric_key) or 0),
                metric_values,
            )
        else:
            score = rank_score(index, len(rows))
        if score_adjustment is not None:
            score = round(score * float(score_adjustment(row)), 1)
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id=dimension_id,
                label=label,
                weight=weight,
                score=score,
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
    pct = row.get("pct_chg", row.get("change_pct", 0))
    return {
        "symbol": row.get("symbol", ""),
        "name": row.get("name", ""),
        "vt_symbol": row.get("vt_symbol", ""),
        "close": row.get("close", 0),
        "pe_ttm": row.get("pe_ttm", 0),
        "pct_chg": pct,
        "change_pct": pct,
        "turnover_rate": row.get("turnover_rate", 0),
        "volume_ratio": row.get("volume_ratio", 0),
        "source": row.get("source", "tushare"),
    }
