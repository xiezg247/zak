"""定时多维度自动选股。"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from vnpy_ashare.calendar import is_trading_day
from vnpy_ashare.jobs.result import JobResult
from vnpy_ashare.market_hours import is_ashare_trading_session, next_quotes_collect_at
from vnpy_ashare.screener.recipe import (
    RECIPE_INTRADAY_MULTI,
    RECIPE_POST_CLOSE_MULTI,
    resolve_recipe,
)
from vnpy_ashare.screener.recipe_runner import build_reason_summary, run_recipe
from vnpy_ashare.screener.runner import ScreenerRunResult

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

_SCREEN_JOB_RECIPES = {
    "screen_intraday": RECIPE_INTRADAY_MULTI,
    "screen_post_close": RECIPE_POST_CLOSE_MULTI,
}


def run_scheduled_auto_screen(job_id: str, *, force: bool = False) -> JobResult:
    from vnpy_ashare.scheduler.config import load_scheduler_config

    default_recipe_id = _SCREEN_JOB_RECIPES.get(job_id)
    if default_recipe_id is None:
        return JobResult(success=False, message=f"未知自动选股任务：{job_id}")

    scheduler_cfg = load_scheduler_config()
    if job_id == "screen_intraday":
        job_cfg = scheduler_cfg.screen_intraday
    else:
        job_cfg = scheduler_cfg.screen_post_close

    recipe_id = job_cfg.recipe_id or default_recipe_id

    recipe = resolve_recipe(recipe_id)
    if recipe is None:
        return JobResult(success=False, message=f"未知选股配方：{recipe_id}")

    now = datetime.now(_SHANGHAI_TZ)
    trigger = f"scheduled_{job_id.removeprefix('screen_')}"

    if job_id == "screen_intraday" and not force:
        if not is_ashare_trading_session(now):
            nxt = next_quotes_collect_at(now, interval_seconds=60)
            return JobResult(
                success=True,
                skipped=True,
                message=f"非交易时段，已跳过（下次 {nxt.strftime('%Y-%m-%d %H:%M:%S')}）",
            )
    elif job_id == "screen_post_close" and not force:
        if not is_trading_day(now.date()):
            return JobResult(
                success=True,
                skipped=True,
                message="非交易日，已跳过",
            )
        if now.time() < time(15, 0):
            return JobResult(
                success=True,
                skipped=True,
                message="尚未收盘，已跳过",
            )

    try:
        result = run_recipe(recipe_id)
    except Exception as ex:
        return JobResult(success=False, message=str(ex))

    if not result.rows:
        return JobResult(
            success=True,
            message=f"{recipe.name} 完成，未命中标的",
        )

    persist_auto_screen_result(
        result,
        trigger=trigger,
        recipe_id=recipe_id,
    )
    summary = build_reason_summary(
        recipe=recipe,
        trigger=trigger,
        row_count=len(result.rows),
    )
    return JobResult(
        success=True,
        message=f"{summary}（扫描约 {result.total_scanned} 只）",
    )


def persist_auto_screen_result(
    result: ScreenerRunResult,
    *,
    trigger: str,
    recipe_id: str,
) -> None:
    from vnpy_ashare.ai.context_store import set_screening_results
    from vnpy_ashare.screener.recipe import resolve_recipe
    from vnpy_ashare.screener.run_store import save_run

    recipe = resolve_recipe(recipe_id)
    rows = list(result.rows)
    config: dict = {
        "trigger": trigger,
        "recipe_id": recipe_id,
        "reason_summary": build_reason_summary(
            recipe=recipe,
            trigger=trigger,
            row_count=len(rows),
        )
        if recipe is not None
        else trigger,
    }
    set_screening_results(
        condition=result.condition,
        rows=rows,
        updated_at=result.updated_at,
    )
    save_run(
        condition=result.condition,
        source=result.source,
        rows=rows,
        total_scanned=result.total_scanned,
        config=config,
    )
