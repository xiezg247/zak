"""同花顺概念板块预拉（ths_index / ths_daily / ths_member 缓存）。"""

from __future__ import annotations

from vnpy_ashare.integrations.tushare import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.integrations.tushare.concept_board import (
    build_hot_concept_vt_symbol_map,
    fetch_ths_concept_index_map,
    fetch_ths_daily_pct_map,
)
from vnpy_ashare.jobs.progress import job_log
from vnpy_ashare.jobs.result import JobResult


def prefetch_concept_board() -> JobResult:
    """预热同花顺概念指数与强势概念成分映射。"""
    try:
        get_tushare_pro()
    except TushareNotConfiguredError as ex:
        return JobResult(success=True, skipped=True, message=str(ex))

    job_log("拉取同花顺概念指数与当日行情…")
    concept_map = fetch_ths_concept_index_map()
    if not concept_map:
        return JobResult(success=False, message="未拉取到同花顺概念列表（可能权限不足）")

    pct_map = fetch_ths_daily_pct_map()
    vt_map, hot_names = build_hot_concept_vt_symbol_map(top_concepts=5)
    return JobResult(
        success=True,
        message=(
            f"概念指数 {len(concept_map)} 个，当日行情 {len(pct_map)} 条，"
            f"强势概念 {len(hot_names)} 个，成分映射 {len(vt_map)} 只"
        ),
    )
