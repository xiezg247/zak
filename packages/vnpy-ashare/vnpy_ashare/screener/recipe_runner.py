"""多维度选股配方执行。

各维度独立打分后按权重合并 ``composite_score``；须命中 ``min_dimensions`` 个维度才入选。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from vnpy_ashare.data.download_concurrency import run_parallel_map
from vnpy_ashare.screener.data_source import (
    fetch_fundamental_screening_rows,
    fetch_moneyflow_with_fallback,
    load_screening_quote_snapshot,
)
from vnpy_ashare.screener.export import resolve_export_columns
from vnpy_ashare.screener.presets import SCREENER_CHANGE_TOP, SCREENER_TURNOVER
from vnpy_ashare.screener.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.recipe import DimensionSpec, ScreenRecipe, resolve_recipe
from vnpy_ashare.screener.rules import (
    apply_low_pe,
    apply_moneyflow_in,
    apply_quote_preset,
)
from vnpy_ashare.screener.runner import ScreenerRunResult

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


@dataclass
class _DimensionHit:
    vt_symbol: str
    dimension_id: str
    label: str
    weight: float
    score: float
    reason: str
    row: dict[str, Any]


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
    hits_by_symbol: dict[str, list[_DimensionHit]] = {}
    total_scanned = 0

    dimension_results = _run_all_dimensions(recipe.dimensions, recipe.pool_size)
    for _spec, dimension_hits, scanned in dimension_results:
        total_scanned = max(total_scanned, scanned)
        for hit in dimension_hits:
            hits_by_symbol.setdefault(hit.vt_symbol, []).append(hit)

    merged_rows: list[dict[str, Any]] = []
    for _vt_symbol, hits in hits_by_symbol.items():
        if len(hits) < recipe.min_dimensions:
            continue
        weight_sum = sum(item.weight for item in hits)
        composite = sum(item.score * item.weight for item in hits) / max(weight_sum, 1e-6)
        base = _merge_rows([item.row for item in hits])
        reasons = [item.reason for item in hits]
        base["composite_score"] = round(composite, 1)
        base["hit_reasons"] = reasons
        base["hit_reason"] = reasons[0] if len(reasons) == 1 else "；".join(reasons[:2])
        base["dimensions"] = {item.dimension_id: round(item.score, 1) for item in hits}
        base["source"] = "recipe"
        merged_rows.append(base)

    merged_rows.sort(
        key=lambda row: (
            float(row.get("composite_score") or 0),
            len(row.get("hit_reasons") or []),
        ),
        reverse=True,
    )
    rows = merged_rows[: max(1, min(int(limit), 200))]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return ScreenerRunResult(
        rows=rows,
        condition=f"{condition_prefix} · {recipe.name}",
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
) -> list[tuple[DimensionSpec, list[_DimensionHit], int]]:
    if not specs:
        return []

    workers = recipe_dimension_max_workers(dimension_count=len(specs))
    if workers <= 1 or len(specs) <= 1:
        return [(spec, *_run_dimension(spec, pool_size)) for spec in specs]

    def worker(spec: DimensionSpec) -> tuple[DimensionSpec, list[_DimensionHit], int]:
        hits, scanned = _run_dimension(spec, pool_size)
        return spec, hits, scanned

    return run_parallel_map(specs, worker, max_workers=workers)


def _run_dimension(
    spec: DimensionSpec,
    pool_size: int,
) -> tuple[list[_DimensionHit], int]:
    if spec.dimension_id == "momentum":
        return _dimension_momentum(pool_size, weight=spec.weight)
    if spec.dimension_id == "turnover":
        return _dimension_turnover(pool_size, weight=spec.weight)
    if spec.dimension_id == "moneyflow":
        return _dimension_moneyflow(pool_size, weight=spec.weight)
    if spec.dimension_id == "low_pe":
        return _dimension_low_pe(pool_size, weight=spec.weight)
    return [], 0


def _dimension_momentum(pool_size: int, *, weight: float) -> tuple[list[_DimensionHit], int]:
    try:
        snapshot = load_screening_quote_snapshot()
        rows = apply_quote_preset(SCREENER_CHANGE_TOP, snapshot.rows, top_n=pool_size)
        return _quote_hits(
            rows,
            dimension_id="momentum",
            label="动量",
            weight=weight,
            reason_builder=lambda row, rank: f"动量：涨幅 {float(row.get('change_pct') or 0):+.2f}%，排名第 {rank}",
        ), snapshot.total
    except MarketQuotesLoadError:
        raw_rows, trade_date, _ = fetch_fundamental_screening_rows()
        if not raw_rows:
            return [], 0
        sorted_rows = sorted(
            raw_rows,
            key=lambda item: float(item.get("pct_chg") or item.get("change_pct") or 0),
            reverse=True,
        )[:pool_size]
        hits: list[_DimensionHit] = []
        for index, row in enumerate(sorted_rows, start=1):
            vt_symbol = str(row.get("vt_symbol") or "")
            if not vt_symbol:
                continue
            pct = float(row.get("pct_chg") or row.get("change_pct") or 0)
            score = _rank_score(index, len(sorted_rows))
            hits.append(
                _DimensionHit(
                    vt_symbol=vt_symbol,
                    dimension_id="momentum",
                    label="动量",
                    weight=weight,
                    score=score,
                    reason=f"动量：日涨幅 {pct:+.2f}%，排名第 {index}",
                    row=_fundamental_base_row(row),
                )
            )
        return hits, len(raw_rows)


def _dimension_turnover(pool_size: int, *, weight: float) -> tuple[list[_DimensionHit], int]:
    try:
        snapshot = load_screening_quote_snapshot()
        rows = apply_quote_preset(SCREENER_TURNOVER, snapshot.rows, top_n=pool_size)
        return _quote_hits(
            rows,
            dimension_id="turnover",
            label="换手",
            weight=weight,
            reason_builder=lambda row, rank: f"换手：{float(row.get('turnover_rate') or 0):.2f}%，排名第 {rank}",
        ), snapshot.total
    except MarketQuotesLoadError:
        return [], 0


def _dimension_moneyflow(pool_size: int, *, weight: float) -> tuple[list[_DimensionHit], int]:
    raw_rows, _trade_date = fetch_moneyflow_with_fallback()
    if not raw_rows:
        return [], 0
    rows = apply_moneyflow_in(raw_rows, top_n=pool_size)
    hits: list[_DimensionHit] = []
    for index, row in enumerate(rows, start=1):
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        amount = float(row.get("net_mf_amount") or 0)
        hits.append(
            _DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id="moneyflow",
                label="资金",
                weight=weight,
                score=_rank_score(index, len(rows)),
                reason=f"资金：主力净流入 {amount:,.0f} 万，排名第 {index}",
                row=dict(row),
            )
        )
    return hits, len(raw_rows)


def _dimension_low_pe(pool_size: int, *, weight: float) -> tuple[list[_DimensionHit], int]:
    raw_rows, _trade_date, _ = fetch_fundamental_screening_rows()
    if not raw_rows:
        return [], 0
    rows = apply_low_pe(raw_rows, top_n=pool_size)
    hits: list[_DimensionHit] = []
    for index, row in enumerate(rows, start=1):
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        pe = float(row.get("pe_ttm") or 0)
        hits.append(
            _DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id="low_pe",
                label="估值",
                weight=weight,
                score=_rank_score(index, len(rows)),
                reason=f"估值：PE(TTM) {pe:.2f}，排名第 {index}",
                row=dict(row),
            )
        )
    return hits, len(raw_rows)


def _quote_hits(
    rows: list[dict[str, Any]],
    *,
    dimension_id: str,
    label: str,
    weight: float,
    reason_builder,
) -> list[_DimensionHit]:
    hits: list[_DimensionHit] = []
    for index, row in enumerate(rows, start=1):
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        hits.append(
            _DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id=dimension_id,
                label=label,
                weight=weight,
                score=_rank_score(index, len(rows)),
                reason=reason_builder(row, index),
                row=dict(row),
            )
        )
    return hits


def _rank_score(rank: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(max(0.0, (total - rank + 1) / total * 100), 1)


def _merge_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for row in rows:
        for key, value in row.items():
            if key in merged and merged[key] not in (None, "", 0):
                continue
            if value not in (None, ""):
                merged[key] = value
    return merged


def _fundamental_base_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": row.get("symbol", ""),
        "name": row.get("name", ""),
        "vt_symbol": row.get("vt_symbol", ""),
        "close": row.get("close", 0),
        "pe_ttm": row.get("pe_ttm", 0),
        "pct_chg": row.get("pct_chg", row.get("change_pct", 0)),
        "turnover_rate": row.get("turnover_rate", 0),
        "source": row.get("source", "tushare"),
    }
