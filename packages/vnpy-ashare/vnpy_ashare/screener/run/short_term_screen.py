"""极致短线编排选股（择时 → 统一配方 → 可选主池）。"""

from __future__ import annotations

from vnpy_ashare.domain.screener.recipe import RECIPE_ULTRA_SHORT_UNIFIED
from vnpy_ashare.domain.screener.result_row import coerce_screener_result_row
from vnpy_ashare.domain.screener.run_result import ScreenerRunResult, build_screener_run_result
from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot
from vnpy_ashare.screener.recipe.recipe_runner import run_recipe
from vnpy_ashare.screener.run.ultra_short_pool_filter import filter_ultra_short_main_pool

__all__ = ["run_short_term_screen"]


def run_short_term_screen(
    *,
    top_n: int = 12,
    variant: str = "mainline",
    require_resonance: bool = False,
    ultra_short_only: bool = True,
) -> ScreenerRunResult:
    """编排极致短线选股：情绪 gate → ultra_short_unified 配方 → 可选共振交集 → 可选主池过滤。"""
    _ = variant  # 统一配方固定主线龙头池；保留参数兼容 vnpy-radar 工具
    top_n = max(1, min(int(top_n or 12), 200))

    cycle = load_emotion_cycle_snapshot(fetch_if_missing=True)
    if cycle is not None and cycle.stage in {"recession", "ice"}:
        stage = cycle.stage_label
        return build_screener_run_result(
            rows=[],
            condition=f"极致短线（{stage}·不宜新开）",
            updated_at=format_china_datetime(),
            total_scanned=0,
            source="short_term",
        )

    recipe_top_n = max(top_n * 2, top_n) if require_resonance else top_n
    recipe_result = run_recipe(
        RECIPE_ULTRA_SHORT_UNIFIED,
        top_n=recipe_top_n,
        condition_prefix="极致短线",
    )
    rows = [coerce_screener_result_row(row) for row in recipe_result.rows]

    if require_resonance:
        rows = [row for row in rows if isinstance(row.get("dimensions"), dict) and "radar_resonance" in row.get("dimensions", {})]

    if ultra_short_only and rows:
        rows = filter_ultra_short_main_pool(rows)

    rows = rows[:top_n]
    condition = "极致短线·雷达统一"
    if cycle is not None:
        condition += f" · {cycle.stage_label}"
    if require_resonance:
        condition += " · 共振"
    if ultra_short_only:
        condition += " · 主池"

    return build_screener_run_result(
        rows=rows,
        condition=condition,
        updated_at=format_china_datetime(),
        total_scanned=recipe_result.total_scanned,
        source="short_term",
    )
