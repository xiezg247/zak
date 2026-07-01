"""动量维度：相对行业 / 大盘强度排行。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRow, QuoteRowLike, coerce_quote_row, quote_row_copy
from vnpy_ashare.screener.data.data_source import fetch_fundamental_screening_rows, load_screening_quote_snapshot
from vnpy_ashare.screener.data.market_benchmark import market_benchmark_change_pct, relative_strength_pct, resolve_relative_strength
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.data.screening_context import get_stock_industry_map
from vnpy_ashare.screener.dimensions.base import DimensionHit, dimension_hit_row, fundamental_base_row, quote_hits
from vnpy_ashare.screener.dimensions.history_signals import attach_momentum_persistence, load_history_bars_map, momentum_persistence_score_factor
from vnpy_ashare.screener.dimensions.scoring import blended_score
from vnpy_ashare.screener.hard_filters import apply_recipe_filters
from vnpy_ashare.screener.sector.sector_summary import attach_industry


def run_momentum(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.engine.dimensions.momentum import build_momentum_hit_rows, score_momentum_rows_polars

    try:
        snapshot = load_screening_quote_snapshot()
        industry_map = get_stock_industry_map()
        enriched = attach_industry(snapshot.rows, industry_map=industry_map)
        market_benchmark = market_benchmark_change_pct(enriched or snapshot.rows)
        scored_rows = score_momentum_rows_polars(list(snapshot.rows), market_benchmark=market_benchmark)
        filtered_rows = apply_recipe_filters(scored_rows)
        filtered_rows.sort(key=lambda item: float(item.get("relative_strength") or 0), reverse=True)
        top_for_history = filtered_rows[: pool_size * 2]
        bars_map = load_history_bars_map([str(item.get("vt_symbol") or "") for item in top_for_history if item.get("vt_symbol")])
        attach_momentum_persistence(top_for_history, bars_map)
        hit_rows = build_momentum_hit_rows(filtered_rows, pool_size=pool_size, market_benchmark=market_benchmark)
        persistence_by_vt = {str(item.get("vt_symbol") or ""): item for item in top_for_history}
        enriched_hits: list[QuoteRow] = []
        for row in hit_rows:
            persisted = persistence_by_vt.get(str(row.get("vt_symbol") or ""))
            if persisted and persisted.get("momentum_positive_days") is not None:
                enriched_hits.append(quote_row_copy(row, momentum_positive_days=int(persisted["momentum_positive_days"])))
            else:
                enriched_hits.append(row)
        return quote_hits(
            enriched_hits,
            dimension_id="momentum",
            label="动量",
            weight=weight,
            metric_key="relative_strength",
            reason_builder=lambda row, rank: _momentum_reason(row, rank),
            score_adjustment=momentum_persistence_score_factor,
        ), snapshot.total
    except MarketQuotesLoadError:
        return _momentum_from_fundamentals(pool_size, weight=weight)


def _momentum_from_fundamentals(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    raw_rows, _trade_date, _ = fetch_fundamental_screening_rows()
    if not raw_rows:
        return [], 0

    from vnpy_ashare.screener.data.screening_context import apply_board_prefilter_rows

    raw_rows = apply_board_prefilter_rows(raw_rows)
    if not raw_rows:
        return [], 0

    industry_map = get_stock_industry_map()
    enriched = attach_industry(raw_rows, industry_map=industry_map)
    market_benchmark = market_benchmark_change_pct(enriched or raw_rows)
    from vnpy_ashare.screener.data.market_benchmark import industry_avg_change_map

    industry_avg = industry_avg_change_map(enriched)
    from vnpy_ashare.screener.dimensions.momentum_bounds import momentum_change_bounds as _momentum_change_bounds

    min_change, max_change = _momentum_change_bounds()
    scored: list[tuple[dict[str, Any], float, str]] = []
    for enriched_row in enriched:
        item = coerce_quote_row(enriched_row).to_dict()
        change = float(item.get("change_pct") or item.get("pct_chg") or 0)
        if not (min_change <= change <= max_change):
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
    for index, (scored_row, rs, basis) in enumerate(top, start=1):
        vt_symbol = str(scored_row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        base_row = quote_row_copy(
            fundamental_base_row(scored_row),
            relative_strength=rs,
            strength_basis=basis,
            benchmark_change_pct=market_benchmark,
            market_relative_strength=float(scored_row.get("market_relative_strength") or 0),
        )
        if scored_row.get("industry_relative_strength") is not None:
            base_row["industry_relative_strength"] = float(scored_row["industry_relative_strength"])
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id="momentum",
                label="动量",
                weight=weight,
                score=blended_score(index, len(top), rs, strength_values),
                reason=_momentum_reason(base_row, index),
                row=dimension_hit_row(base_row),
            )
        )
    return hits, len(raw_rows)


def _momentum_reason(row: QuoteRowLike, rank: int) -> str:
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
