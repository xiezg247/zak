"""APScheduler 任务调度管理。"""

from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

from apscheduler.events import EVENT_JOB_MAX_INSTANCES
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from vnpy_ashare.domain.datetime import china_now, format_china_datetime
from vnpy_ashare.domain.market_hours import is_ashare_trading_session, next_quotes_collect_at
from vnpy_ashare.jobs.batch_fill_downloaded import batch_fill_downloaded_stale_job
from vnpy_ashare.jobs.concept_prefetch import prefetch_concept_board
from vnpy_ashare.jobs.disclosure_sync import sync_disclosure_calendar_job
from vnpy_ashare.jobs.financial_sync import sync_watchlist_financials_job
from vnpy_ashare.jobs.market_summary_warmup import warm_market_summary
from vnpy_ashare.jobs.moneyflow_prefetch import prefetch_moneyflow
from vnpy_ashare.jobs.quotes import collect_market_quotes
from vnpy_ashare.jobs.sector_flow_sync import sync_sector_flow_daily_job
from vnpy_ashare.jobs.stock_industry import sync_stock_industry_job
from vnpy_ashare.jobs.suspend_sync import sync_suspend_daily_job
from vnpy_ashare.jobs.trade_calendar import sync_trade_calendar_job
from vnpy_ashare.jobs.tushare_prefetch import prefetch_tushare_factors
from vnpy_ashare.jobs.universe import sync_universe_job
from vnpy_ashare.jobs.universe_download import batch_download_universe_daily_bars
from vnpy_ashare.jobs.auto_screen import run_scheduled_auto_screen
from vnpy_ashare.jobs.horizon_scan import run_horizon_outlook_scan_job
from vnpy_ashare.jobs.progress import bind_job_log
from vnpy_ashare.jobs.result import JobResult
from vnpy_ashare.scheduler.config import (
    AutoScreenJobConfig,
    JobConfig,
    SchedulerConfig,
    load_scheduler_config,
    save_scheduler_config,
)
from vnpy_ashare.scheduler.job_meta import load_job_run_meta, save_job_run_meta
from vnpy_ashare.screener.recipe.recipe import resolve_recipe

_COLLECT_QUOTES_JOB_ID = "collect_quotes"
_COLLECT_QUOTES_INTERVAL_MIN = 5

logger = logging.getLogger(__name__)
_MAX_RUN_LOG = 200
_MAX_RUN_DETAIL_LINES = 400

SchedulerJobConfig = JobConfig | AutoScreenJobConfig


def _recipe_label(recipe_id: str, fallback: str) -> str:
    recipe = resolve_recipe(recipe_id or fallback)
    if recipe is None:
        return recipe_id or fallback
    prefix = "内置" if recipe.builtin else "我的"
    return f"{prefix} · {recipe.name}"


def _normalize_cron_hours(raw: str, *, default: str = "10,14") -> str:
    """APScheduler CronTrigger.hour 须为逗号分隔字符串，不能传 list。"""
    parts = [part.strip() for part in str(raw or "").split(",") if part.strip()]
    if not parts:
        return default
    return ",".join(parts)


@dataclass
class JobRunRecord:
    finished_at: str
    job_id: str
    job_name: str
    success: bool
    message: str
    skipped: bool = False
    started_at: str | None = None
    running: bool = False
    detail_lines: list[str] = field(default_factory=list)


@dataclass
class JobStatus:
    job_id: str
    name: str
    description: str
    schedule_text: str
    enabled: bool
    running: bool = False
    last_run_at: str | None = None
    last_message: str | None = None
    last_success: bool | None = None
    next_run_at: str | None = None


@dataclass
class _JobMeta:
    job_id: str
    name: str
    description: str
    runner: Callable[[], JobResult]
    config_attr: str
    schedule_builder: Callable[[Any], Any]
    schedule_text_builder: Callable[[Any], str]


class TaskSchedulerManager:
    """后台定时任务：行情采集 / 同步标的 / 批量下载。"""

    EVENT_JOB_UPDATED = "eAshareJobUpdated"

    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        self._config = load_scheduler_config()
        self._running_jobs: set[str] = set()
        self._lock = threading.Lock()
        self._status: dict[str, JobStatus] = {}
        self._listeners: list[Callable[[str], None]] = []
        self._job_finished_hooks: list[Callable[[str, JobResult], None]] = []
        self._run_log: deque[JobRunRecord] = deque(maxlen=_MAX_RUN_LOG)

        self._jobs: dict[str, _JobMeta] = {
            "collect_quotes": _JobMeta(
                job_id="collect_quotes",
                name="行情采集",
                description="TickFlow 全市场快照写入 Redis（开发调试用，生产建议独立进程）",
                runner=collect_market_quotes,
                config_attr="collect_quotes",
                schedule_builder=lambda cfg: IntervalTrigger(seconds=max(cfg.interval_seconds, _COLLECT_QUOTES_INTERVAL_MIN)),
                schedule_text_builder=lambda cfg: f"交易时段内每 {max(cfg.interval_seconds, _COLLECT_QUOTES_INTERVAL_MIN)} 秒；非交易时段自动休眠",
            ),
            "sync_universe": _JobMeta(
                job_id="sync_universe",
                name="同步 A 股列表",
                description="从 TickFlow 更新全市场标的到本地 SQLite",
                runner=sync_universe_job,
                config_attr="sync_universe",
                schedule_builder=lambda cfg: CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=cfg.cron_hour,
                    minute=cfg.cron_minute,
                ),
                schedule_text_builder=lambda cfg: f"每周 {cfg.cron_day_of_week} {cfg.cron_hour:02d}:{cfg.cron_minute:02d}",
            ),
            "sync_stock_industry": _JobMeta(
                job_id="sync_stock_industry",
                name="同步行业映射",
                description="从 Tushare stock_basic 拉取申万行业分类，供市场页行业榜与行业筛选",
                runner=sync_stock_industry_job,
                config_attr="sync_stock_industry",
                schedule_builder=lambda cfg: CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=cfg.cron_hour,
                    minute=cfg.cron_minute,
                ),
                schedule_text_builder=lambda cfg: f"每周 {cfg.cron_day_of_week} {cfg.cron_hour:02d}:{cfg.cron_minute:02d}",
            ),
            "sync_trade_calendar": _JobMeta(
                job_id="sync_trade_calendar",
                name="同步交易日历",
                description="从 Tushare 更新 A 股交易日历到本地 SQLite",
                runner=sync_trade_calendar_job,
                config_attr="sync_trade_calendar",
                schedule_builder=lambda cfg: CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=cfg.cron_hour,
                    minute=cfg.cron_minute,
                ),
                schedule_text_builder=lambda cfg: f"每周 {cfg.cron_day_of_week} {cfg.cron_hour:02d}:{cfg.cron_minute:02d}",
            ),
            "batch_download_universe": _JobMeta(
                job_id="batch_download_universe",
                name="全市场日 K",
                description="从 Tushare 为全 A 股下载/补全自 2020 年以来的日 K；增量由「补全本地日 K」维护",
                runner=self._run_universe_daily_download,
                config_attr="batch_download_universe",
                schedule_builder=lambda cfg: CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=cfg.cron_hour,
                    minute=cfg.cron_minute,
                ),
                schedule_text_builder=lambda cfg: f"工作日 {cfg.cron_hour:02d}:{cfg.cron_minute:02d}，起始于 {cfg.download_start}",
            ),
            "prefetch_moneyflow": _JobMeta(
                job_id="prefetch_moneyflow",
                name="主力资金预拉",
                description="收盘后从 Tushare 拉取全市场 moneyflow 主力资金流向，供雷达与个股分析",
                runner=prefetch_moneyflow,
                config_attr="prefetch_moneyflow",
                schedule_builder=lambda cfg: CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=cfg.cron_hour,
                    minute=cfg.cron_minute,
                ),
                schedule_text_builder=lambda cfg: f"工作日 {cfg.cron_hour:02d}:{cfg.cron_minute:02d}（建议早于 Tushare 因子预拉）",
            ),
            "sync_sector_flow_daily": _JobMeta(
                job_id="sync_sector_flow_daily",
                name="板块资金同步",
                description="收盘后拉取东财行业/同花顺概念近 N 日板块资金流，写入 sector_flow_daily 供详情页近5日柱图",
                runner=sync_sector_flow_daily_job,
                config_attr="sync_sector_flow_daily",
                schedule_builder=lambda cfg: CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=cfg.cron_hour,
                    minute=cfg.cron_minute,
                ),
                schedule_text_builder=lambda cfg: f"工作日 {cfg.cron_hour:02d}:{cfg.cron_minute:02d}（建议在主力资金预拉之后）",
            ),
            "sync_suspend_daily": _JobMeta(
                job_id="sync_suspend_daily",
                name="停牌日同步",
                description="收盘后从 Tushare 增量拉取最近交易日全市场停牌记录，供日 K 断层扫描排除",
                runner=sync_suspend_daily_job,
                config_attr="sync_suspend_daily",
                schedule_builder=lambda cfg: CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=cfg.cron_hour,
                    minute=cfg.cron_minute,
                ),
                schedule_text_builder=lambda cfg: f"工作日 {cfg.cron_hour:02d}:{cfg.cron_minute:02d}（建议在主力资金预拉之后）",
            ),
            "prefetch_tushare": _JobMeta(
                job_id="prefetch_tushare",
                name="Tushare 因子预拉",
                description="收盘后拉取 daily_basic、涨跌停、指数、北向、stock_basic 等写入本地缓存",
                runner=self._run_prefetch_tushare,
                config_attr="prefetch_tushare",
                schedule_builder=lambda cfg: CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=cfg.cron_hour,
                    minute=cfg.cron_minute,
                ),
                schedule_text_builder=lambda cfg: f"工作日 {cfg.cron_hour:02d}:{cfg.cron_minute:02d}（建议早于盘后自动选股）",
            ),
            "prefetch_concept_board": _JobMeta(
                job_id="prefetch_concept_board",
                name="概念板块预拉",
                description="预热同花顺概念指数、当日行情与强势概念成分映射（雷达概念维度依赖）",
                runner=prefetch_concept_board,
                config_attr="prefetch_concept_board",
                schedule_builder=lambda cfg: CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=cfg.cron_hour,
                    minute=cfg.cron_minute,
                ),
                schedule_text_builder=lambda cfg: f"工作日 {cfg.cron_hour:02d}:{cfg.cron_minute:02d}（建议在 Tushare 因子预拉之后）",
            ),
            "warm_market_summary": _JobMeta(
                job_id="warm_market_summary",
                name="市场摘要预热",
                description="收盘后计算情绪周期与连板梯队并写入内存缓存，供 UI / 风控只读（避免启动阻塞）",
                runner=lambda: warm_market_summary(include_ladder=True),
                config_attr="warm_market_summary",
                schedule_builder=lambda cfg: CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=cfg.cron_hour,
                    minute=cfg.cron_minute,
                ),
                schedule_text_builder=lambda cfg: f"工作日 {cfg.cron_hour:02d}:{cfg.cron_minute:02d}（建议在概念预拉之后；含连板统计）",
            ),
            "sync_watchlist_financials": _JobMeta(
                job_id="sync_watchlist_financials",
                name="同步自选财报",
                description="增量拉取自选池利润表/资产负债表/现金流量表/财务指标到本地",
                runner=sync_watchlist_financials_job,
                config_attr="sync_watchlist_financials",
                schedule_builder=lambda cfg: CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=cfg.cron_hour,
                    minute=cfg.cron_minute,
                ),
                schedule_text_builder=lambda cfg: f"工作日 {cfg.cron_hour:02d}:{cfg.cron_minute:02d}（建议在 Tushare 因子预拉之后）",
            ),
            "sync_disclosure_calendar": _JobMeta(
                job_id="sync_disclosure_calendar",
                name="同步披露计划",
                description="拉取自选池财报预约披露日期，用于驱动财报增量同步",
                runner=sync_disclosure_calendar_job,
                config_attr="sync_disclosure_calendar",
                schedule_builder=lambda cfg: CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=cfg.cron_hour,
                    minute=cfg.cron_minute,
                ),
                schedule_text_builder=lambda cfg: f"工作日 {cfg.cron_hour:02d}:{cfg.cron_minute:02d}（建议在同步自选财报之前）",
            ),
            "batch_fill_stale": _JobMeta(
                job_id="batch_fill_stale",
                name="补全本地日 K",
                description="为本地已下载列表中过期的日 K 增量补全到最近交易日",
                runner=batch_fill_downloaded_stale_job,
                config_attr="batch_fill_stale",
                schedule_builder=lambda cfg: CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=cfg.cron_hour,
                    minute=cfg.cron_minute,
                ),
                schedule_text_builder=lambda cfg: f"工作日 {cfg.cron_hour:02d}:{cfg.cron_minute:02d}（建议在全市场日 K 与补全之后）",
            ),
            "screen_intraday": _JobMeta(
                job_id="screen_intraday",
                name="盘中自动选股",
                description="交易时段多维度选股（动量+换手），结果写入选股历史",
                runner=lambda: run_scheduled_auto_screen("screen_intraday"),
                config_attr="screen_intraday",
                schedule_builder=lambda _cfg: CronTrigger(hour="10,14", minute=0),
                schedule_text_builder=lambda cfg: f"交易日 {cfg.cron_hours}:{cfg.cron_minute_intraday:02d} · {_recipe_label(cfg.recipe_id, 'intraday_multi')}",
            ),
            "screen_post_close": _JobMeta(
                job_id="screen_post_close",
                name="盘后自动选股",
                description="收盘后多维度选股（资金+估值+动量），结果写入选股历史",
                runner=lambda: run_scheduled_auto_screen("screen_post_close"),
                config_attr="screen_post_close",
                schedule_builder=lambda cfg: CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=cfg.cron_hour,
                    minute=cfg.cron_minute,
                ),
                schedule_text_builder=lambda cfg: f"工作日 {cfg.cron_hour:02d}:{cfg.cron_minute:02d} · {_recipe_label(cfg.recipe_id, 'post_close_multi')}",
            ),
            "scan_horizon_outlook": _JobMeta(
                job_id="scan_horizon_outlook",
                name="雷达展望扫描",
                description="收盘后全市场扫描未来·关注/可持/情景/预测，写入本地缓存",
                runner=run_horizon_outlook_scan_job,
                config_attr="scan_horizon_outlook",
                schedule_builder=lambda cfg: CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=cfg.cron_hour,
                    minute=cfg.cron_minute,
                ),
                schedule_text_builder=lambda cfg: f"工作日 {cfg.cron_hour:02d}:{cfg.cron_minute:02d}（建议在盘后自动选股之后）",
            ),
        }
        self._scheduler.add_listener(self._on_job_max_instances, EVENT_JOB_MAX_INSTANCES)
        self._refresh_status_cache()

    def _collect_quotes_interval(self) -> int:
        cfg = cast(JobConfig, self._get_job_config(_COLLECT_QUOTES_JOB_ID))
        return max(cfg.interval_seconds, _COLLECT_QUOTES_INTERVAL_MIN)

    def _run_collect_quotes(self, *, force: bool = False) -> JobResult:
        now = china_now()
        if not force and not is_ashare_trading_session(now):
            nxt = next_quotes_collect_at(
                now,
                interval_seconds=self._collect_quotes_interval(),
            )
            return JobResult(
                success=True,
                skipped=True,
                message=f"非交易时段，已跳过（下次 {nxt.strftime('%Y-%m-%d %H:%M:%S')}）",
            )

        result = collect_market_quotes()
        if result.success and not result.skipped:
            warm = warm_market_summary(include_ladder=False)
            if warm.message:
                result = JobResult(
                    success=result.success,
                    skipped=result.skipped,
                    message=f"{result.message} · {warm.message}",
                )
        if force and not is_ashare_trading_session(now):
            return JobResult(
                success=result.success,
                skipped=False,
                message=f"非交易时段手动采集 · {result.message}",
            )
        return result

    def _run_prefetch_tushare(self) -> JobResult:
        result = prefetch_tushare_factors()
        if not result.success or result.skipped:
            return result
        warm = warm_market_summary(include_ladder=False)
        if warm.message:
            return JobResult(success=result.success, message=f"{result.message} · {warm.message}")
        return result

    def _next_collect_quotes_run_at(self, *, prefer_immediate: bool = False) -> datetime:
        now = china_now()
        if prefer_immediate and is_ashare_trading_session(now):
            return now
        return next_quotes_collect_at(
            now,
            interval_seconds=self._collect_quotes_interval(),
        )

    def _schedule_collect_quotes(self, *, prefer_immediate: bool = False) -> None:
        cfg = self._get_job_config(_COLLECT_QUOTES_JOB_ID)
        if not cfg.enabled:
            return

        run_at = self._next_collect_quotes_run_at(prefer_immediate=prefer_immediate)
        meta = self._jobs[_COLLECT_QUOTES_JOB_ID]
        self._scheduler.add_job(
            self._wrap_job,
            trigger=DateTrigger(run_date=run_at),
            id=_COLLECT_QUOTES_JOB_ID,
            name=meta.name,
            kwargs={"job_id": _COLLECT_QUOTES_JOB_ID, "force": False},
            replace_existing=True,
            max_instances=1,
        )

    def _on_job_max_instances(self, event) -> None:
        job_id = event.job_id.split("__", 1)[0]
        if job_id not in self._jobs:
            return

        status = self._status.get(job_id)
        if status is None:
            return

        status.last_message = "跳过：上一轮仍在执行"
        status.last_success = None
        self._notify(job_id)

    def add_listener(self, callback: Callable[[str], None]) -> None:
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def add_job_finished_hook(self, callback: Callable[[str, JobResult], None]) -> None:
        self._job_finished_hooks.append(callback)

    def get_job_name(self, job_id: str) -> str:
        meta = self._jobs.get(job_id)
        return meta.name if meta is not None else job_id

    def _notify(self, job_id: str) -> None:
        for callback in list(self._listeners):
            try:
                callback(job_id)
            except Exception:
                pass

    def _run_universe_daily_download(self) -> JobResult:
        cfg = self._config.batch_download_universe
        return batch_download_universe_daily_bars(daily_start=cfg.download_start)

    def _get_job_config(self, job_id: str) -> SchedulerJobConfig:
        meta = self._jobs[job_id]
        return cast(SchedulerJobConfig, getattr(self._config, meta.config_attr))

    def _set_job_config(self, job_id: str, job_config: SchedulerJobConfig) -> None:
        meta = self._jobs[job_id]
        setattr(self._config, meta.config_attr, job_config)

    def _resolve_last_run_fields(
        self,
        job_id: str,
    ) -> tuple[str | None, str | None, bool | None]:
        previous = self._status.get(job_id)
        if previous and (previous.running or job_id in self._running_jobs):
            return previous.last_run_at, previous.last_message, previous.last_success
        if previous and previous.last_run_at:
            return previous.last_run_at, previous.last_message, previous.last_success
        persisted = load_job_run_meta(job_id)
        if persisted:
            return persisted.last_run_at, persisted.last_message, persisted.last_success
        if previous:
            return previous.last_run_at, previous.last_message, previous.last_success
        return None, None, None

    def _refresh_status_cache(self) -> None:
        for job_id, meta in self._jobs.items():
            cfg = self._get_job_config(job_id)
            next_run = None
            if self._scheduler.running:
                job = self._scheduler.get_job(job_id)
                if job and job.next_run_time:
                    next_run = format_china_datetime(job.next_run_time)

            last_run_at, last_message, last_success = self._resolve_last_run_fields(job_id)
            self._status[job_id] = JobStatus(
                job_id=job_id,
                name=meta.name,
                description=meta.description,
                schedule_text=meta.schedule_text_builder(cfg),
                enabled=cfg.enabled,
                running=job_id in self._running_jobs,
                last_run_at=last_run_at,
                last_message=last_message,
                last_success=last_success,
                next_run_at=next_run,
            )

    def get_config(self) -> SchedulerConfig:
        return self._config

    def get_job_config(self, job_id: str) -> SchedulerJobConfig:
        return self._get_job_config(job_id)

    def save_config(self) -> None:
        save_scheduler_config(self._config)

    def list_status(self) -> list[JobStatus]:
        self.ensure_started()
        self._refresh_status_cache()
        return [self._status[job_id] for job_id in self._jobs]

    def list_run_log(self, *, limit: int = _MAX_RUN_LOG) -> list[JobRunRecord]:
        if limit <= 0:
            return []
        records = list(self._run_log)
        if limit >= len(records):
            return list(reversed(records))
        return list(reversed(records[-limit:]))

    def get_status(self, job_id: str) -> JobStatus | None:
        self.ensure_started()
        self._refresh_status_cache()
        return self._status.get(job_id)

    def ensure_started(self) -> None:
        """按需启动调度器（冷启动延迟，首次访问时再加载任务）。"""
        if self._scheduler.running:
            return
        self.start()

    def start(self) -> None:
        if self._scheduler.running:
            self.reload_jobs()
            return
        self._scheduler.start()
        self.reload_jobs()

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def reload_jobs(self) -> None:
        for job_id in self._jobs:
            self._remove_job(job_id)
            cfg = self._get_job_config(job_id)
            if not cfg.enabled:
                continue
            if job_id == _COLLECT_QUOTES_JOB_ID:
                if job_id not in self._running_jobs:
                    self._schedule_collect_quotes(prefer_immediate=True)
                continue
            meta = self._jobs[job_id]
            if job_id == "screen_intraday":
                auto_cfg = cast(AutoScreenJobConfig, cfg)
                hours = _normalize_cron_hours(auto_cfg.cron_hours)
                trigger = CronTrigger(
                    day_of_week=auto_cfg.cron_day_of_week,
                    hour=hours,
                    minute=auto_cfg.cron_minute_intraday,
                )
            elif job_id == "screen_post_close":
                trigger = CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=cfg.cron_hour,
                    minute=cfg.cron_minute,
                )
            else:
                trigger = meta.schedule_builder(cfg)
            self._scheduler.add_job(
                self._wrap_job,
                trigger=trigger,
                id=job_id,
                name=meta.name,
                kwargs={"job_id": job_id},
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
        self._refresh_status_cache()
        self._notify("*")

    def _remove_job(self, job_id: str) -> None:
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)

    def set_enabled(self, job_id: str, enabled: bool) -> None:
        self.ensure_started()
        cfg = self._get_job_config(job_id)
        cfg.enabled = enabled
        self.save_config()
        self.reload_jobs()

    def update_job_config(self, job_id: str, **kwargs: Any) -> None:
        self.ensure_started()
        cfg = self._get_job_config(job_id)
        for key, value in kwargs.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        self.save_config()
        self.reload_jobs()

    def _append_run_detail(self, record: JobRunRecord, message: str) -> None:
        text = str(message).strip()
        if not text:
            return
        with self._lock:
            record.detail_lines.append(text)
            if len(record.detail_lines) > _MAX_RUN_DETAIL_LINES:
                record.detail_lines = record.detail_lines[-_MAX_RUN_DETAIL_LINES:]
            status = self._status.get(record.job_id)
            if status is not None:
                status.last_message = text[:240]
        self._notify(record.job_id)

    def _begin_run_log(self, job_id: str, meta: _JobMeta) -> JobRunRecord:
        started_at = format_china_datetime()
        record = JobRunRecord(
            started_at=started_at,
            finished_at=started_at,
            job_id=job_id,
            job_name=meta.name,
            success=True,
            message="执行中…",
            running=True,
        )
        self._run_log.append(record)
        status = self._status.get(job_id)
        if status is not None:
            status.last_message = "执行中…"
        return record

    def _finalize_run_log(
        self,
        record: JobRunRecord,
        *,
        message: str,
        success: bool,
        skipped: bool,
    ) -> None:
        finished_at = format_china_datetime()
        record.running = False
        record.finished_at = finished_at
        record.message = message
        record.success = success if not skipped else True
        record.skipped = skipped

    def run_now(self, job_id: str) -> bool:
        if job_id not in self._jobs:
            return False
        if job_id in self._running_jobs:
            return False
        self.ensure_started()
        force = job_id in (
            _COLLECT_QUOTES_JOB_ID,
            "screen_intraday",
            "screen_post_close",
            "scan_horizon_outlook",
        )
        self._scheduler.add_job(
            self._wrap_job,
            kwargs={"job_id": job_id, "force": force},
            id=f"{job_id}__manual__{datetime.now().timestamp()}",
            replace_existing=False,
            max_instances=1,
        )
        return True

    def _wrap_job(self, job_id: str, force: bool = False) -> None:
        meta = self._jobs[job_id]
        with self._lock:
            if job_id in self._running_jobs:
                return
            self._running_jobs.add(job_id)
        self._refresh_status_cache()
        self._notify(job_id)

        record = self._begin_run_log(job_id, meta)
        reset_log = bind_job_log(lambda msg: self._append_run_detail(record, msg))
        self._append_run_detail(record, f"[开始] {meta.name}")

        skipped = False
        success = False
        message = ""
        try:
            if job_id == _COLLECT_QUOTES_JOB_ID:
                result = self._run_collect_quotes(force=force)
            elif job_id in ("screen_intraday", "screen_post_close"):
                result = run_scheduled_auto_screen(job_id, force=force)
            elif job_id == "scan_horizon_outlook":
                result = run_horizon_outlook_scan_job(force=force)
            else:
                result = meta.runner()
            message = result.message
            skipped = result.skipped
            success = result.success if not skipped else True
        except Exception as ex:
            message = str(ex)
            success = False
        finally:
            reset_log()

        mark = "跳过" if skipped else ("成功" if success else "失败")
        self._append_run_detail(record, f"[结束] {mark} · {message}")
        self._finalize_run_log(record, message=message, success=success, skipped=skipped)

        finished_at = record.finished_at
        status = self._status.get(job_id)
        if status:
            status.last_run_at = finished_at
            status.last_message = message
            status.last_success = None if skipped else success
            status.running = False

        save_job_run_meta(
            job_id,
            last_run_at=finished_at,
            last_message=message,
            last_success=None if skipped else success,
        )

        with self._lock:
            self._running_jobs.discard(job_id)

        self._refresh_status_cache()
        self._notify(job_id)

        finished = JobResult(success=success, message=message, skipped=skipped)
        for hook in list(self._job_finished_hooks):
            try:
                hook(job_id, finished)
            except Exception:
                logger.exception("job_finished_hook failed job_id=%s", job_id)

        if job_id == _COLLECT_QUOTES_JOB_ID and self._get_job_config(job_id).enabled:
            self._schedule_collect_quotes()
