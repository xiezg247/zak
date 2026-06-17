"""维度执行共用类型与工具。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import Field, field_validator

from vnpy_ashare.domain.market.quote_row import QuoteRow, QuoteRowLike, coerce_quote_row, quote_row_copy
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.screener.dimensions.scoring import blended_score, rank_score
from vnpy_common.domain.base import MutableModel


class DimensionHit(MutableModel):
    """单维度命中记录。"""

    vt_symbol: str = Field(description="标的 vt_symbol")
    dimension_id: str = Field(description="维度标识")
    label: str = Field(description="维度展示名")
    weight: float = Field(description="维度权重")
    score: float = Field(description="维度得分")
    reason: str = Field(description="命中原因")
    row: ScreenerResultRow = Field(description="结构化行情行（含维度扩展列）")

    @field_validator("row", mode="before")
    @classmethod
    def _coerce_hit_row(cls, value: Any) -> ScreenerResultRow:
        return dimension_hit_row(value)


def dimension_hit_row(row: QuoteRowLike | ScreenerResultRow | dict[str, Any]) -> ScreenerResultRow:
    """维度命中行归一化为 ``ScreenerResultRow``。"""
    if isinstance(row, ScreenerResultRow):
        return row
    if isinstance(row, dict):
        return ScreenerResultRow.from_mapping(row)
    return ScreenerResultRow.from_quote_row(coerce_quote_row(row))


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
                row=dimension_hit_row(row),
            )
        )
    return hits


def merge_rows(rows: Sequence[ScreenerResultRow | dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for row in rows:
        payload = row.to_dict() if isinstance(row, ScreenerResultRow) else dict(row)
        for key, value in payload.items():
            if key in merged and merged[key] not in (None, "", 0):
                continue
            if value not in (None, ""):
                merged[key] = value
    return merged


def fundamental_base_row(row: QuoteRowLike) -> QuoteRow:
    pct = row.get("pct_chg", row.get("change_pct", 0))
    result = quote_row_copy(
        row,
        symbol=str(row.get("symbol") or ""),
        name=str(row.get("name") or ""),
        vt_symbol=str(row.get("vt_symbol") or ""),
        close=float(row.get("close") or 0),
        change_pct=float(pct or 0),
        turnover_rate=float(row.get("turnover_rate") or 0),
        volume_ratio=float(row.get("volume_ratio") or 0),
        source=str(row.get("source") or "tushare"),
    )
    if row.get("pe_ttm") not in (None, ""):
        result["pe_ttm"] = float(row.get("pe_ttm") or 0)
    if pct not in (None, ""):
        result["pct_chg"] = float(pct or 0)
    return result
