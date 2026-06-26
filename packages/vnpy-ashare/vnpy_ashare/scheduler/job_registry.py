"""调度器任务注册表：从 catalog 元数据构建 APScheduler 任务描述。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pydantic import ConfigDict, Field

from vnpy_ashare.jobs.bars.batch_fill import batch_fill_downloaded_stale_job
from vnpy_ashare.jobs.bars.focus_pool_minute import batch_fill_focus_pool_minute_job
from vnpy_ashare.jobs.catalog import (
    BILIBILI_SYNC_INTERVAL_SECONDS,
    COLLECT_QUOTES_INTERVAL_SECONDS,
    COLLECT_QUOTES_JOB_ID,
    JOBS_BY_ID,
)
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.jobs.financial.disclosure import sync_disclosure_calendar_job
from vnpy_ashare.jobs.financial.sync import sync_watchlist_financials_job
from vnpy_ashare.jobs.market.summary_warmup import warm_market_summary
from vnpy_ashare.jobs.prefetch.concept import prefetch_concept_board
from vnpy_ashare.jobs.prefetch.moneyflow import prefetch_moneyflow
from vnpy_ashare.jobs.prefetch.sector_flow import sync_sector_flow_daily_job
from vnpy_ashare.jobs.quotes.collect import collect_market_quotes
from vnpy_ashare.jobs.radar.card_snapshot_warmup import warm_radar_card_snapshots_job
from vnpy_ashare.jobs.screen.auto_screen import run_scheduled_auto_screen
from vnpy_ashare.jobs.screen.horizon_scan import run_horizon_outlook_scan_job
from vnpy_ashare.jobs.sync.stock_industry import sync_stock_industry_job
from vnpy_ashare.jobs.sync.suspend_sync import sync_suspend_daily_job
from vnpy_ashare.jobs.sync.trade_calendar import sync_trade_calendar_job
from vnpy_ashare.jobs.sync.universe import sync_universe_job
from vnpy_ashare.screener.recipe.recipe import resolve_recipe
from vnpy_common.domain.base import MutableModel


def recipe_label(recipe_id: str, fallback: str) -> str:
    recipe = resolve_recipe(recipe_id or fallback)
    if recipe is None:
        return recipe_id or fallback
    prefix = "内置" if recipe.builtin else "我的"
    return f"{prefix} · {recipe.name}"


class SchedulerJobMeta(MutableModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    job_id: str = Field(description="任务 ID")
    name: str = Field(description="任务名称")
    description: str = Field(description="任务说明")
    runner: Callable[[], JobResult] = Field(description="任务执行函数")
    config_attr: str = Field(description="SchedulerConfig 属性名")
    schedule_builder: Callable[[Any], Any] = Field(description="构建 APScheduler trigger")
    schedule_text_builder: Callable[[Any], str] = Field(description="构建调度说明文案")


@dataclass(frozen=True, slots=True)
class SchedulerJobRunners:
    """需调度器上下文才能执行的 runner。"""

    run_universe_daily_download: Callable[[], JobResult]
    run_prefetch_tushare: Callable[[], JobResult]
    run_sync_bilibili_feed: Callable[[], JobResult]
    run_warm_watchlist_strategy_cache: Callable[[], JobResult]


def _weekly_cron_trigger(cfg: Any) -> CronTrigger:
    return CronTrigger(
        day_of_week=cfg.cron_day_of_week,
        hour=cfg.cron_hour,
        minute=cfg.cron_minute,
    )


def _weekly_schedule_text(cfg: Any) -> str:
    return f"每周 {cfg.cron_day_of_week} {cfg.cron_hour:02d}:{cfg.cron_minute:02d}"


def _workday_schedule_text(cfg: Any, *, suffix: str = "") -> str:
    text = f"工作日 {cfg.cron_hour:02d}:{cfg.cron_minute:02d}"
    return f"{text}{suffix}" if suffix else text


def build_scheduler_jobs(runners: SchedulerJobRunners) -> dict[str, SchedulerJobMeta]:
    """从 catalog 元数据与上下文 runner 构建调度任务表。"""
    specs = JOBS_BY_ID
    return {
        COLLECT_QUOTES_JOB_ID: SchedulerJobMeta(
            job_id=COLLECT_QUOTES_JOB_ID,
            name=specs[COLLECT_QUOTES_JOB_ID].name,
            description=specs[COLLECT_QUOTES_JOB_ID].description,
            runner=collect_market_quotes,
            config_attr=specs[COLLECT_QUOTES_JOB_ID].config_attr,
            schedule_builder=lambda cfg: IntervalTrigger(
                seconds=max(cfg.interval_seconds, COLLECT_QUOTES_INTERVAL_SECONDS),
            ),
            schedule_text_builder=lambda cfg: f"交易时段内每 {max(cfg.interval_seconds, COLLECT_QUOTES_INTERVAL_SECONDS)} 秒；非交易时段自动休眠",
        ),
        "sync_universe": SchedulerJobMeta(
            job_id="sync_universe",
            name=specs["sync_universe"].name,
            description=specs["sync_universe"].description,
            runner=sync_universe_job,
            config_attr=specs["sync_universe"].config_attr,
            schedule_builder=_weekly_cron_trigger,
            schedule_text_builder=_weekly_schedule_text,
        ),
        "sync_stock_industry": SchedulerJobMeta(
            job_id="sync_stock_industry",
            name=specs["sync_stock_industry"].name,
            description=specs["sync_stock_industry"].description,
            runner=sync_stock_industry_job,
            config_attr=specs["sync_stock_industry"].config_attr,
            schedule_builder=_weekly_cron_trigger,
            schedule_text_builder=_weekly_schedule_text,
        ),
        "sync_trade_calendar": SchedulerJobMeta(
            job_id="sync_trade_calendar",
            name=specs["sync_trade_calendar"].name,
            description=specs["sync_trade_calendar"].description,
            runner=sync_trade_calendar_job,
            config_attr=specs["sync_trade_calendar"].config_attr,
            schedule_builder=_weekly_cron_trigger,
            schedule_text_builder=_weekly_schedule_text,
        ),
        "batch_download_universe": SchedulerJobMeta(
            job_id="batch_download_universe",
            name=specs["batch_download_universe"].name,
            description=specs["batch_download_universe"].description,
            runner=runners.run_universe_daily_download,
            config_attr=specs["batch_download_universe"].config_attr,
            schedule_builder=_weekly_cron_trigger,
            schedule_text_builder=lambda cfg: f"工作日 {cfg.cron_hour:02d}:{cfg.cron_minute:02d}，起始于 {cfg.download_start}",
        ),
        "prefetch_moneyflow": SchedulerJobMeta(
            job_id="prefetch_moneyflow",
            name=specs["prefetch_moneyflow"].name,
            description=specs["prefetch_moneyflow"].description,
            runner=prefetch_moneyflow,
            config_attr=specs["prefetch_moneyflow"].config_attr,
            schedule_builder=_weekly_cron_trigger,
            schedule_text_builder=lambda cfg: _workday_schedule_text(cfg, suffix="（建议早于 Tushare 因子预拉）"),
        ),
        "sync_sector_flow_daily": SchedulerJobMeta(
            job_id="sync_sector_flow_daily",
            name=specs["sync_sector_flow_daily"].name,
            description=specs["sync_sector_flow_daily"].description,
            runner=sync_sector_flow_daily_job,
            config_attr=specs["sync_sector_flow_daily"].config_attr,
            schedule_builder=_weekly_cron_trigger,
            schedule_text_builder=lambda cfg: _workday_schedule_text(cfg, suffix="（建议在主力资金预拉之后）"),
        ),
        "sync_suspend_daily": SchedulerJobMeta(
            job_id="sync_suspend_daily",
            name=specs["sync_suspend_daily"].name,
            description=specs["sync_suspend_daily"].description,
            runner=sync_suspend_daily_job,
            config_attr=specs["sync_suspend_daily"].config_attr,
            schedule_builder=_weekly_cron_trigger,
            schedule_text_builder=lambda cfg: _workday_schedule_text(cfg, suffix="（建议在主力资金预拉之后）"),
        ),
        "prefetch_tushare": SchedulerJobMeta(
            job_id="prefetch_tushare",
            name=specs["prefetch_tushare"].name,
            description=specs["prefetch_tushare"].description,
            runner=runners.run_prefetch_tushare,
            config_attr=specs["prefetch_tushare"].config_attr,
            schedule_builder=_weekly_cron_trigger,
            schedule_text_builder=lambda cfg: _workday_schedule_text(cfg, suffix="（建议早于盘后自动选股）"),
        ),
        "prefetch_concept_board": SchedulerJobMeta(
            job_id="prefetch_concept_board",
            name=specs["prefetch_concept_board"].name,
            description=specs["prefetch_concept_board"].description,
            runner=prefetch_concept_board,
            config_attr=specs["prefetch_concept_board"].config_attr,
            schedule_builder=_weekly_cron_trigger,
            schedule_text_builder=lambda cfg: _workday_schedule_text(cfg, suffix="（建议在 Tushare 因子预拉之后）"),
        ),
        "warm_market_summary": SchedulerJobMeta(
            job_id="warm_market_summary",
            name=specs["warm_market_summary"].name,
            description=specs["warm_market_summary"].description,
            runner=lambda: warm_market_summary(enrich_factors=True),
            config_attr=specs["warm_market_summary"].config_attr,
            schedule_builder=_weekly_cron_trigger,
            schedule_text_builder=lambda cfg: _workday_schedule_text(cfg, suffix="（建议在概念预拉之后）"),
        ),
        "warm_watchlist_strategy_cache": SchedulerJobMeta(
            job_id="warm_watchlist_strategy_cache",
            name=specs["warm_watchlist_strategy_cache"].name,
            description=specs["warm_watchlist_strategy_cache"].description,
            runner=runners.run_warm_watchlist_strategy_cache,
            config_attr=specs["warm_watchlist_strategy_cache"].config_attr,
            schedule_builder=_weekly_cron_trigger,
            schedule_text_builder=lambda cfg: _workday_schedule_text(cfg, suffix="（建议在日 K 补全之后）"),
        ),
        "warm_radar_card_snapshots": SchedulerJobMeta(
            job_id="warm_radar_card_snapshots",
            name=specs["warm_radar_card_snapshots"].name,
            description=specs["warm_radar_card_snapshots"].description,
            runner=warm_radar_card_snapshots_job,
            config_attr=specs["warm_radar_card_snapshots"].config_attr,
            schedule_builder=lambda cfg: IntervalTrigger(seconds=max(cfg.interval_seconds, 300)),
            schedule_text_builder=lambda cfg: (
                f"交易日每 {max(cfg.interval_seconds, 300) // 60} 分钟（仅交易时段执行）"
            ),
        ),
        "sync_watchlist_financials": SchedulerJobMeta(
            job_id="sync_watchlist_financials",
            name=specs["sync_watchlist_financials"].name,
            description=specs["sync_watchlist_financials"].description,
            runner=sync_watchlist_financials_job,
            config_attr=specs["sync_watchlist_financials"].config_attr,
            schedule_builder=_weekly_cron_trigger,
            schedule_text_builder=lambda cfg: _workday_schedule_text(cfg, suffix="（建议在 Tushare 因子预拉之后）"),
        ),
        "sync_disclosure_calendar": SchedulerJobMeta(
            job_id="sync_disclosure_calendar",
            name=specs["sync_disclosure_calendar"].name,
            description=specs["sync_disclosure_calendar"].description,
            runner=sync_disclosure_calendar_job,
            config_attr=specs["sync_disclosure_calendar"].config_attr,
            schedule_builder=_weekly_cron_trigger,
            schedule_text_builder=lambda cfg: _workday_schedule_text(cfg, suffix="（建议在同步自选财报之前）"),
        ),
        "batch_fill_stale": SchedulerJobMeta(
            job_id="batch_fill_stale",
            name=specs["batch_fill_stale"].name,
            description=specs["batch_fill_stale"].description,
            runner=batch_fill_downloaded_stale_job,
            config_attr=specs["batch_fill_stale"].config_attr,
            schedule_builder=_weekly_cron_trigger,
            schedule_text_builder=lambda cfg: _workday_schedule_text(cfg, suffix="（建议在全市场日 K 与补全之后）"),
        ),
        "fill_focus_pool_minute": SchedulerJobMeta(
            job_id="fill_focus_pool_minute",
            name=specs["fill_focus_pool_minute"].name,
            description=specs["fill_focus_pool_minute"].description,
            runner=batch_fill_focus_pool_minute_job,
            config_attr=specs["fill_focus_pool_minute"].config_attr,
            schedule_builder=_weekly_cron_trigger,
            schedule_text_builder=lambda cfg: _workday_schedule_text(cfg, suffix="（建议在日 K 补全之后）"),
        ),
        "screen_intraday": SchedulerJobMeta(
            job_id="screen_intraday",
            name=specs["screen_intraday"].name,
            description=specs["screen_intraday"].description,
            runner=lambda: run_scheduled_auto_screen("screen_intraday"),
            config_attr=specs["screen_intraday"].config_attr,
            schedule_builder=lambda _cfg: CronTrigger(hour="10,14", minute=0),
            schedule_text_builder=lambda cfg: f"交易日 {cfg.cron_hours}:{cfg.cron_minute_intraday:02d} · {recipe_label(cfg.recipe_id, 'intraday_multi')}",
        ),
        "screen_post_close": SchedulerJobMeta(
            job_id="screen_post_close",
            name=specs["screen_post_close"].name,
            description=specs["screen_post_close"].description,
            runner=lambda: run_scheduled_auto_screen("screen_post_close"),
            config_attr=specs["screen_post_close"].config_attr,
            schedule_builder=_weekly_cron_trigger,
            schedule_text_builder=lambda cfg: f"工作日 {cfg.cron_hour:02d}:{cfg.cron_minute:02d} · {recipe_label(cfg.recipe_id, 'post_close_multi')}",
        ),
        "scan_horizon_outlook": SchedulerJobMeta(
            job_id="scan_horizon_outlook",
            name=specs["scan_horizon_outlook"].name,
            description=specs["scan_horizon_outlook"].description,
            runner=run_horizon_outlook_scan_job,
            config_attr=specs["scan_horizon_outlook"].config_attr,
            schedule_builder=_weekly_cron_trigger,
            schedule_text_builder=lambda cfg: _workday_schedule_text(cfg, suffix="（建议在盘后自动选股之后）"),
        ),
        "sync_bilibili_feed": SchedulerJobMeta(
            job_id="sync_bilibili_feed",
            name=specs["sync_bilibili_feed"].name,
            description=specs["sync_bilibili_feed"].description,
            runner=runners.run_sync_bilibili_feed,
            config_attr=specs["sync_bilibili_feed"].config_attr,
            schedule_builder=lambda cfg: IntervalTrigger(
                seconds=max(cfg.interval_seconds, BILIBILI_SYNC_INTERVAL_SECONDS),
            ),
            schedule_text_builder=lambda cfg: f"每天 08:00–20:00 每 {max(cfg.interval_seconds, BILIBILI_SYNC_INTERVAL_SECONDS) // 60} 分钟",
        ),
    }
