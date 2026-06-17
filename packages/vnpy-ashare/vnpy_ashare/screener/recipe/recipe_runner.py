"""多维度选股配方执行。

各维度独立打分后按权重合并 ``composite_score``；须命中 ``min_dimensions`` 个维度才入选。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from vnpy_ashare.data.download_concurrency import run_parallel_map
from vnpy_ashare.quotes.market.moneyflow_kind import (
    enrich_moneyflow_row_with_kind,
    moneyflow_dimension_score_factor,
    row_has_moneyflow_fields,
)
from vnpy_ashare.screener.data.data_source import enrich_recipe_rows
from vnpy_ashare.screener.data.screening_context import preload_screening_context, screening_context_scope
from vnpy_ashare.screener.dimensions.base import DimensionHit, merge_rows
from vnpy_ashare.screener.dimensions.registry import run_dimension, scoring_dimension_specs
from vnpy_ashare.screener.dimensions.volume_dedup import apply_volume_liquidity_dedup
from vnpy_ashare.screener.hard_filters import apply_recipe_filters
from vnpy_ashare.screener.recipe.recipe import RECIPE_EMOTION_GATE_ONLY, DimensionSpec, ScreenRecipe, resolve_recipe
from vnpy_ashare.screener.run.export import resolve_export_columns
from vnpy_ashare.screener.run.runner import ScreenerRunResult
from vnpy_ashare.screener.sentiment.sentiment_gate import (
    apply_emotion_gate_only_finalize,
    apply_sentiment_modulation,
    sentiment_gate_enabled,
)

DEFAULT_RECIPE_DIMENSION_MAX_WORKERS = 4


def recipe_dimension_max_workers(*, dimension_count: int) -> int:
    """配方维度并行数（RECIPE_DIMENSION_MAX_WORKERS，默认 4，上限 8）。"""
    raw = os.getenv("RECIPE_DIMENSION_MAX_WORKERS", str(DEFAULT_RECIPE_DIMENSION_MAX_WORKERS)).strip()
    try:
        configured = int(raw)
    except ValueError:
        configured = DEFAULT_RECIPE_DIMENSION_MAX_WORKERS
    configured = max(1, min(configured, 8))
    return min(configured, dimension_count)


def run_recipe(
    recipe_id: str,
    *,
    top_n: int | None = None,
    condition_prefix: str = "自动",
) -> ScreenerRunResult:
    """按 recipe_id 执行多因子选股。"""
    recipe = resolve_recipe(recipe_id)
    if recipe is None:
        raise ValueError(f"未知选股配方：{recipe_id}")
    return run_recipe_object(
        recipe,
        top_n=top_n,
        condition_prefix=condition_prefix,
    )


def run_recipe_object(
    recipe: ScreenRecipe,
    *,
    top_n: int | None = None,
    condition_prefix: str = "配方",
) -> ScreenerRunResult:
    """执行配方对象：各维度取 pool_size 候选，加权合并后取 top_n。"""
    limit = top_n or recipe.top_n
    hits_by_symbol: dict[str, list[DimensionHit]] = {}
    total_scanned = 0

    with screening_context_scope() as ctx:
        preload_screening_context(ctx)
        scoring_specs = scoring_dimension_specs(list(recipe.dimensions))
        dimension_results = _run_all_dimensions(scoring_specs, recipe.pool_size)
        for _spec, dimension_hits, scanned in dimension_results:
            total_scanned = max(total_scanned, scanned)
            for hit in dimension_hits:
                hits_by_symbol.setdefault(hit.vt_symbol, []).append(hit)

    merged_rows: list[dict[str, Any]] = []
    for _vt_symbol, hits in hits_by_symbol.items():
        if len(hits) < recipe.min_dimensions:
            continue
        hits = apply_volume_liquidity_dedup(hits)
        weight_sum = sum(item.weight for item in hits)
        composite = sum(item.score * item.weight * moneyflow_dimension_score_factor(item.dimension_id, item.row) for item in hits) / max(weight_sum, 1e-6)
        base = merge_rows([item.row for item in hits])
        if row_has_moneyflow_fields(base):
            base = enrich_moneyflow_row_with_kind(base)
        reasons = [item.reason for item in hits]
        base["composite_score"] = round(composite, 1)
        base["hit_reasons"] = reasons
        base["hit_reason"] = reasons[0] if len(reasons) == 1 else "；".join(reasons[:2])
        base["dimensions"] = {item.dimension_id: round(item.score, 1) for item in hits}
        base["source"] = "recipe"
        merged_rows.append(base)

    merged_rows = enrich_recipe_rows(merged_rows)
    merged_rows.sort(
        key=lambda row: (
            float(row.get("composite_score") or 0),
            len(row.get("hit_reasons") or []),
        ),
        reverse=True,
    )
    merged_rows = apply_recipe_filters(merged_rows)
    use_sentiment = sentiment_gate_enabled() and (
        recipe.trigger_kind == "intraday"
        or any(spec.dimension_id == "sentiment_gate" for spec in recipe.dimensions)
        or recipe.recipe_id == RECIPE_EMOTION_GATE_ONLY
    )
    merged_rows, _sentiment_meta = apply_sentiment_modulation(merged_rows, enabled=use_sentiment)

    gate_meta: dict[str, Any] | None = None
    if recipe.recipe_id == RECIPE_EMOTION_GATE_ONLY:
        merged_rows, gate_meta = apply_emotion_gate_only_finalize(merged_rows, top_n=limit)

    rows = merged_rows[: max(1, min(int(limit), 200))]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    condition = f"{condition_prefix} · {recipe.name}"
    if gate_meta and gate_meta.get("gate_message"):
        condition += f" · {gate_meta['gate_message']}"

    return ScreenerRunResult(
        rows=rows,
        condition=condition,
        updated_at=now,
        total_scanned=total_scanned,
        source="recipe",
        columns=resolve_export_columns(rows),
    )


def build_reason_summary(*, recipe: ScreenRecipe, trigger: str, row_count: int) -> str:
    """定时任务落库用的一行摘要（触发源 + 配方名 + 维度 + 命中数）。"""
    trigger_label = {
        "scheduled_intraday": "盘中自动",
        "scheduled_post_close": "盘后自动",
    }.get(trigger, trigger)
    dims = " + ".join(spec.label for spec in recipe.dimensions)
    return f"{trigger_label} · {recipe.name}（{dims}）· 命中 {row_count} 条"


def _run_all_dimensions(
    specs: list[DimensionSpec],
    pool_size: int,
) -> list[tuple[DimensionSpec, list[DimensionHit], int]]:
    if not specs:
        return []

    workers = recipe_dimension_max_workers(dimension_count=len(specs))
    if workers <= 1 or len(specs) <= 1:
        return [(spec, *run_dimension(spec, pool_size)) for spec in specs]

    def worker(spec: DimensionSpec) -> tuple[DimensionSpec, list[DimensionHit], int]:
        hits, scanned = run_dimension(spec, pool_size)
        return spec, hits, scanned

    return run_parallel_map(specs, worker, max_workers=workers)
