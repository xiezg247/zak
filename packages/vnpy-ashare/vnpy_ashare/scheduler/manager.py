"""APScheduler 任务调度管理。"""

from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from apscheduler.events import EVENT_JOB_MAX_INSTANCES
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from pydantic import Field

from vnpy_ashare.domain.time.china import china_now, format_china_datetime
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session, next_quotes_collect_at
from vnpy_ashare.jobs.bars.download import batch_download_universe_daily_bars
from vnpy_ashare.jobs.catalog import COLLECT_QUOTES_JOB_ID, MANUAL_FORCE_JOB_IDS
from vnpy_ashare.jobs.core.progress import bind_job_log
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.jobs.runners import (
    collect_quotes_interval_seconds,
    run_collect_quotes,
    run_job,
    run_prefetch_tushare_with_warm,
    run_sync_bilibili_feed,
)
from vnpy_ashare.jobs.watchlist.strategy_prewarm import warm_watchlist_strategy_cache_job
from vnpy_ashare.scheduler.config import (
    AutoScreenJobConfig,
    JobConfig,
    SchedulerConfig,
    load_scheduler_config,
    save_scheduler_config,
)
from vnpy_ashare.scheduler.job_meta import load_job_run_meta, save_job_run_meta
from vnpy_ashare.scheduler.job_registry import SchedulerJobMeta, SchedulerJobRunners, build_scheduler_jobs
from vnpy_ashare.scheduler.leader import is_user_scoped_job, run_job_for_active_users, should_run_scheduler
from vnpy_common.domain.base import MutableModel

if TYPE_CHECKING:
    from vnpy_ashare.app.engine import AshareEngine

logger = logging.getLogger(__name__)
_MAX_RUN_LOG = 200
_MAX_RUN_DETAIL_LINES = 400

SchedulerJobConfig = JobConfig | AutoScreenJobConfig


def _normalize_cron_hours(raw: str, *, default: str = "10,14") -> str:
    """APScheduler CronTrigger.hour 须为逗号分隔字符串，不能传 list。"""
    parts = [part.strip() for part in str(raw or "").split(",") if part.strip()]
    if not parts:
        return default
    return ",".join(parts)


class JobRunRecord(MutableModel):
    finished_at: str = Field(description="结束时间")
    job_id: str = Field(description="任务 ID")
    job_name: str = Field(description="任务名称")
    success: bool = Field(description="是否成功")
    message: str = Field(description="结果摘要")
    skipped: bool = Field(default=False, description="是否跳过")
    started_at: str | None = Field(default=None, description="开始时间")
    running: bool = Field(default=False, description="是否执行中")
    detail_lines: list[str] = Field(default_factory=list, description="详细日志行")


class JobStatus(MutableModel):
    job_id: str = Field(description="任务 ID")
    name: str = Field(description="任务名称")
    description: str = Field(description="任务说明")
    schedule_text: str = Field(description="调度说明文案")
    enabled: bool = Field(description="是否启用")
    running: bool = Field(default=False, description="是否执行中")
    last_run_at: str | None = Field(default=None, description="上次执行时间")
    last_message: str | None = Field(default=None, description="上次执行摘要")
    last_success: bool | None = Field(default=None, description="上次是否成功")
    next_run_at: str | None = Field(default=None, description="下次执行时间")


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
        self._engine: AshareEngine | None = None
        self._defer_immediate_collect = True

        self._jobs: dict[str, SchedulerJobMeta] = build_scheduler_jobs(
            SchedulerJobRunners(
                run_universe_daily_download=self._run_universe_daily_download,
                run_prefetch_tushare=self._run_prefetch_tushare,
                run_sync_bilibili_feed=lambda: self._run_sync_bilibili_feed(),
                run_warm_watchlist_strategy_cache=lambda: warm_watchlist_strategy_cache_job(
                    engine=self._engine,
                ),
            ),
        )
        self._scheduler.add_listener(self._on_job_max_instances, EVENT_JOB_MAX_INSTANCES)
        self._refresh_status_cache()

    def _collect_quotes_interval(self) -> int:
        return collect_quotes_interval_seconds()

    def _run_collect_quotes(self, *, force: bool = False) -> JobResult:
        return run_collect_quotes(force=force)

    def _run_prefetch_tushare(self) -> JobResult:
        return run_prefetch_tushare_with_warm()

    def _run_sync_bilibili_feed(self, *, force: bool = False) -> JobResult:
        return run_sync_bilibili_feed(force=force, engine=self._engine)

    def _next_collect_quotes_run_at(self, *, prefer_immediate: bool = False) -> datetime:
        now = china_now()
        if prefer_immediate and is_ashare_trading_session(now):
            return now
        return next_quotes_collect_at(
            now,
            interval_seconds=self._collect_quotes_interval(),
        )

    def _schedule_collect_quotes(self, *, prefer_immediate: bool = False) -> None:
        cfg = self._get_job_config(COLLECT_QUOTES_JOB_ID)
        if not cfg.enabled:
            return

        run_at = self._next_collect_quotes_run_at(prefer_immediate=prefer_immediate)
        meta = self._jobs[COLLECT_QUOTES_JOB_ID]
        self._scheduler.add_job(
            self._wrap_job,
            trigger=DateTrigger(run_date=run_at),
            id=COLLECT_QUOTES_JOB_ID,
            name=meta.name,
            kwargs={"job_id": COLLECT_QUOTES_JOB_ID, "force": False},
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

    def bind_engine(self, engine: AshareEngine) -> None:
        self._engine = engine

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
        if should_run_scheduler():
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
        if should_run_scheduler():
            self.ensure_started()
        self._refresh_status_cache()
        return self._status.get(job_id)

    def ensure_started(self) -> None:
        """按需启动调度器（冷启动延迟，首次访问时再加载任务）。"""
        if not should_run_scheduler():
            return
        if self._scheduler.running:
            return
        self.start()

    def start(self) -> None:
        if not should_run_scheduler():
            logger.info("ZAK_RUN_SCHEDULER 未启用，跳过 APScheduler 启动")
            return
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
            if job_id == COLLECT_QUOTES_JOB_ID:
                if job_id not in self._running_jobs:
                    self._schedule_collect_quotes(prefer_immediate=not self._defer_immediate_collect)
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
        self._defer_immediate_collect = False
        self._refresh_status_cache()
        self._notify("*")

    def _remove_job(self, job_id: str) -> None:
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)

    def set_enabled(self, job_id: str, enabled: bool) -> None:
        if should_run_scheduler():
            self.ensure_started()
        cfg = self._get_job_config(job_id)
        cfg.enabled = enabled
        self.save_config()
        if should_run_scheduler():
            self.reload_jobs()

    def update_job_config(self, job_id: str, **kwargs: Any) -> None:
        if should_run_scheduler():
            self.ensure_started()
        cfg = self._get_job_config(job_id)
        for key, value in kwargs.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        self.save_config()
        if should_run_scheduler():
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

    def _begin_run_log(self, job_id: str, meta: SchedulerJobMeta) -> JobRunRecord:
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
        force = job_id in MANUAL_FORCE_JOB_IDS
        if should_run_scheduler():
            self.ensure_started()
            if self._scheduler.running:
                self._scheduler.add_job(
                    self._wrap_job,
                    kwargs={"job_id": job_id, "force": force},
                    id=f"{job_id}__manual__{datetime.now().timestamp()}",
                    replace_existing=False,
                    max_instances=1,
                )
                return True
        threading.Thread(
            target=self._wrap_job,
            kwargs={"job_id": job_id, "force": force},
            daemon=True,
        ).start()
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
            if is_user_scoped_job(job_id):
                result = run_job_for_active_users(
                    job_id,
                    lambda: run_job(job_id, force=force, engine=self._engine),
                )
            else:
                result = run_job(job_id, force=force, engine=self._engine)
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

        if job_id == COLLECT_QUOTES_JOB_ID and self._get_job_config(job_id).enabled:
            self._schedule_collect_quotes()
