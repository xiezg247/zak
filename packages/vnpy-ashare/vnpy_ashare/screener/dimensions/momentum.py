"""动量维度：相对行业 / 大盘强度排行。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.screener.data.data_source import fetch_fundamental_screening_rows, load_screening_quote_snapshot
from vnpy_ashare.screener.data.market_benchmark import (
    industry_avg_change_map,
    market_benchmark_change_pct,
    relative_strength_pct,
    resolve_relative_strength,
)
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.data.screening_context import get_stock_industry_map
from vnpy_ashare.screener.dimensions.base import DimensionHit, fundamental_base_row, quote_hits
from vnpy_ashare.screener.dimensions.history_signals import (
    attach_momentum_persistence,
    load_history_bars_map,
    momentum_persistence_score_factor,
)
from vnpy_ashare.screener.dimensions.scoring import blended_score
from vnpy_ashare.screener.hard_filters import apply_screening_filters
from vnpy_ashare.screener.preset.rules import _quote_row
from vnpy_ashare.screener.sector.sector_summary import attach_industry
from vnpy_ashare.screener.sentiment.sentiment_gate import try_fetch_fear_greed_index


def _momentum_change_bounds() -> tuple[float, float]:
    import os

    from vnpy_ashare.screener.recipe_tuning_prefs import load_recipe_tuning_prefs

    prefs = load_recipe_tuning_prefs()
    min_raw = os.getenv("MOMENTUM_MIN_CHANGE_PCT", "").strip()
    max_raw = os.getenv("MOMENTUM_MAX_CHANGE_PCT", "").strip()
    fear_max_raw = os.getenv("MOMENTUM_FEAR_MAX_CHANGE_PCT", "").strip()

    min_change = float(min_raw) if min_raw else prefs.momentum_min_change_pct
    max_change = float(max_raw) if max_raw else prefs.momentum_max_change_pct
    fear_max = float(fear_max_raw) if fear_max_raw else prefs.momentum_fear_max_change_pct

    snapshot = try_fetch_fear_greed_index()
    if snapshot is not None and float(snapshot.index) < 30:
        max_change = min(max_change, fear_max)
    return min_change, max_change


def _momentum_change_allowed(change: float) -> bool:
    min_change, max_change = _momentum_change_bounds()
    return min_change <= change <= max_change


def run_momentum(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    try:
        snapshot = load_screening_quote_snapshot()
        industry_map = get_stock_industry_map()
        enriched = attach_industry(snapshot.rows, industry_map=industry_map)
        market_benchmark = market_benchmark_change_pct(enriched or snapshot.rows)
        industry_avg = industry_avg_change_map(enriched)

        scored_rows: list[dict[str, Any]] = []
        for row in enriched:
            merged = dict(row)
            change = float(merged.get("change_pct") or merged.get("pct_chg") or 0)
            if not _momentum_change_allowed(change):
                continue
            rs, basis = resolve_relative_strength(
                merged,
                market_benchmark=market_benchmark,
                industry_avg_map=industry_avg,
            )
            merged["benchmark_change_pct"] = market_benchmark
            merged["relative_strength"] = rs
            merged["strength_basis"] = basis
            merged["market_relative_strength"] = relative_strength_pct(merged, market_benchmark)
            if merged.get("industry") and str(merged.get("industry")) in industry_avg:
                industry_avg_pct = float(industry_avg[str(merged["industry"])])
                merged["industry_relative_strength"] = relative_strength_pct(merged, industry_avg_pct)
            scored_rows.append(merged)

        scored_rows = apply_screening_filters(scored_rows)
        scored_rows.sort(key=lambda item: float(item.get("relative_strength") or 0), reverse=True)
        top_for_history = scored_rows[: pool_size * 2]
        bars_map = load_history_bars_map([str(item.get("vt_symbol") or "") for item in top_for_history if item.get("vt_symbol")])
        attach_momentum_persistence(top_for_history, bars_map)
        rows: list[dict[str, Any]] = []
        for item in scored_rows[:pool_size]:
            base = _quote_row(item)
            base["benchmark_change_pct"] = market_benchmark
            base["relative_strength"] = float(item.get("relative_strength") or 0)
            base["strength_basis"] = str(item.get("strength_basis") or "大盘")
            base["market_relative_strength"] = float(item.get("market_relative_strength") or 0)
            if item.get("industry_relative_strength") is not None:
                base["industry_relative_strength"] = float(item["industry_relative_strength"])
            if item.get("industry"):
                base["industry"] = item["industry"]
            rows.append(base)

        return quote_hits(
            rows,
            dimension_id="momentum",
            label="动量",
            weight=weight,
            metric_key="relative_strength",
            reason_builder=lambda row, rank: _momentum_reason(row, rank),
            score_adjustment=momentum_persistence_score_factor,
        ), snapshot.total
    except MarketQuotesLoadError:
        raw_rows, _trade_date, _ = fetch_fundamental_screening_rows()
        if not raw_rows:
            return [], 0
        industry_map = get_stock_industry_map()
        enriched = attach_industry(raw_rows, industry_map=industry_map)
        market_benchmark = market_benchmark_change_pct(enriched or raw_rows)
        industry_avg = industry_avg_change_map(enriched)
        scored: list[tuple[dict[str, Any], float, str]] = []
        for row in enriched:
            item = dict(row)
            change = float(item.get("change_pct") or item.get("pct_chg") or 0)
            if not _momentum_change_allowed(change):
                continue
            rs, basis = resolve_relative_strength(
                item,
                market_benchmark=market_benchmark,
                industry_avg_map=industry_avg,
            )
            item["relative_strength"] = rs
            item["strength_basis"] = basis
            item["benchmark_change_pct"] = market_benchmark
            item["market_relative_strength"] = relative_strength_pct(item, market_benchmark)
            if item.get("industry") and str(item.get("industry")) in industry_avg:
                industry_avg_pct = float(industry_avg[str(item["industry"])])
                item["industry_relative_strength"] = relative_strength_pct(item, industry_avg_pct)
            scored.append((item, rs, basis))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        top = scored[:pool_size]
        strength_values = [rs for _, rs, _ in top]
        hits: list[DimensionHit] = []
        for index, (row, rs, basis) in enumerate(top, start=1):
            vt_symbol = str(row.get("vt_symbol") or "")
            if not vt_symbol:
                continue
            base_row = fundamental_base_row(row)
            base_row["relative_strength"] = rs
            base_row["strength_basis"] = basis
            base_row["benchmark_change_pct"] = market_benchmark
            base_row["market_relative_strength"] = float(row.get("market_relative_strength") or 0)
            if row.get("industry_relative_strength") is not None:
                base_row["industry_relative_strength"] = float(row["industry_relative_strength"])
            hits.append(
                DimensionHit(
                    vt_symbol=vt_symbol,
                    dimension_id="momentum",
                    label="动量",
                    weight=weight,
                    score=blended_score(index, len(top), rs, strength_values),
                    reason=_momentum_reason(base_row, index),
                    row=base_row,
                )
            )
        return hits, len(raw_rows)


def _momentum_reason(row: dict[str, Any], rank: int) -> str:
    change = float(row.get("change_pct") or row.get("pct_chg") or 0)
    rs = float(row.get("relative_strength") or 0)
    basis = str(row.get("strength_basis") or "大盘")
    benchmark = float(row.get("benchmark_change_pct") or 0)
    market_rs = float(row.get("market_relative_strength") or relative_strength_pct(row, benchmark))
    industry_rs = row.get("industry_relative_strength")
    persistence_note = ""
    positive_days = row.get("momentum_positive_days")
    if positive_days is not None:
        persistence_note = f"，近5日收涨 {int(positive_days)} 天"
    if basis.startswith("行业") and industry_rs is not None:
        return f"动量：涨幅 {change:+.2f}%，相对{basis} {float(industry_rs):+.2f}%，相对大盘 {market_rs:+.2f}%{persistence_note}，排名第 {rank}"
    return f"动量：涨幅 {change:+.2f}%，相对大盘 {rs:+.2f}%（基准 {benchmark:+.2f}%）{persistence_note}，排名第 {rank}"
