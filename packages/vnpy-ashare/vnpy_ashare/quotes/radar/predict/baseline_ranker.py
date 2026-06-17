"""雷达预测：Phase 0 截面因子加权基线（非 ML）。"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRowLike, quote_row_copy
from vnpy_ashare.domain.screener.predict import BaselinePredictHit
from vnpy_ashare.screener.data.market_benchmark import (
    industry_avg_change_map,
    market_benchmark_change_pct,
    resolve_relative_strength,
)
from vnpy_ashare.screener.data.screening_context import get_stock_industry_map
from vnpy_ashare.screener.sector.sector_summary import attach_industry

_WEIGHT_RS = 0.40
_WEIGHT_MOMENTUM = 0.30
_WEIGHT_VOLUME = 0.20
_WEIGHT_TURNOVER = 0.10

PREDICT_HORIZON_DAYS = 5


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _percentile_rank(values: list[float], target: float) -> float:
    if not values:
        return 0.5
    below = sum(1 for value in values if value < target)
    equal = sum(1 for value in values if value == target)
    return _clamp((below + equal * 0.5) / len(values), 0.0, 1.0)


def _sigmoid_p_up(score: float) -> float:
    """将 0–100 基准分映射为看涨概率（校准占位，非回测最优）。"""
    x = (score - 50.0) / 12.0
    return _clamp(1.0 / (1.0 + math.exp(-x)), 0.05, 0.95)


def _prepare_rows(rows: Sequence[QuoteRowLike]) -> list[dict[str, Any]]:
    industry_map = get_stock_industry_map()
    enriched = attach_industry(rows, industry_map=industry_map)
    market_benchmark = market_benchmark_change_pct(enriched or rows)
    industry_avg = industry_avg_change_map(enriched)
    prepared: list[dict[str, Any]] = []
    for row in enriched:
        rs, _basis = resolve_relative_strength(
            row,
            market_benchmark=market_benchmark,
            industry_avg_map=industry_avg,
        )
        merged = quote_row_copy(
            row,
            predict_relative_strength=float(rs),
            predict_change_pct=float(row.get("change_pct") or row.get("pct_chg") or 0),
            predict_volume_ratio=float(row.get("volume_ratio") or 1.0),
            predict_turnover_rate=float(row.get("turnover_rate") or 0.0),
        )
        prepared.append(merged.to_dict())
    return prepared


def rank_baseline_predict(rows: Sequence[QuoteRowLike]) -> list[BaselinePredictHit]:
    """对候选池做截面百分位加权，返回按 score 降序的预测命中。"""
    prepared = _prepare_rows(rows)
    if not prepared:
        return []

    rs_values = [float(row["predict_relative_strength"]) for row in prepared]
    mom_values = [float(row["predict_change_pct"]) for row in prepared]
    vol_values = [float(row["predict_volume_ratio"]) for row in prepared]
    turnover_values = [float(row["predict_turnover_rate"]) for row in prepared]

    hits: list[BaselinePredictHit] = []
    for row in prepared:
        vt_symbol = str(row.get("vt_symbol") or "").strip()
        if not vt_symbol:
            continue
        rs = float(row["predict_relative_strength"])
        change = float(row["predict_change_pct"])
        volume_ratio = float(row["predict_volume_ratio"])
        turnover = float(row["predict_turnover_rate"])
        composite = (
            _percentile_rank(rs_values, rs) * _WEIGHT_RS
            + _percentile_rank(mom_values, change) * _WEIGHT_MOMENTUM
            + _percentile_rank(vol_values, volume_ratio) * _WEIGHT_VOLUME
            + _percentile_rank(turnover_values, turnover) * _WEIGHT_TURNOVER
        )
        score = round(composite * 100.0, 1)
        hits.append(
            BaselinePredictHit(
                vt_symbol=vt_symbol,
                score=score,
                p_up=round(_sigmoid_p_up(score), 3),
                relative_strength=round(rs, 2),
                change_pct=round(change, 2),
                volume_ratio=round(volume_ratio, 2),
                turnover_rate=round(turnover, 2),
            )
        )
    hits.sort(key=lambda item: (-item.score, -item.p_up, item.vt_symbol))
    return hits
