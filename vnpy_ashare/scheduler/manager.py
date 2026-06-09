"""APScheduler 任务调度管理。"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.events import EVENT_JOB_MAX_INSTANCES
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from vnpy_ashare.jobs import (
    JobResult,
    batch_download_watchlist,
    collect_market_quotes,
    sync_universe_job,
)
from vnpy_ashare.jobs.auto_screen import run_scheduled_auto_screen
from vnpy_ashare.market_hours import is_ashare_trading_session, next_quotes_collect_at
from vnpy_ashare.scheduler.config import JobConfig, SchedulerConfig, load_scheduler_config, save_scheduler_config

_COLLECT_QUOTES_JOB_ID = "collect_quotes"
_COLLECT_QUOTES_INTERVAL_MIN = 5
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_MAX_RUN_LOG = 200


@dataclass
class JobRunRecord:
    finished_at: str
    job_id: str
    job_name: str
    success: bool
    message: str
    skipped: bool = False


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
        self._run_log: deque[JobRunRecord] = deque(maxlen=_MAX_RUN_LOG)

        self._jobs: dict[str, _JobMeta] = {
            "collect_quotes": _JobMeta(
                job_id="collect_quotes",
                name="行情采集",
                description="TickFlow 全市场快照写入 Redis（开发调试用，生产建议独立进程）",
                runner=collect_market_quotes,
                config_attr="collect_quotes",
                schedule_builder=lambda cfg: IntervalTrigger(
                    seconds=max(cfg.interval_seconds, _COLLECT_QUOTES_INTERVAL_MIN)
                ),
                schedule_text_builder=lambda cfg: (
                    f"交易时段内每 {max(cfg.interval_seconds, _COLLECT_QUOTES_INTERVAL_MIN)} 秒；"
                    "非交易时段自动休眠"
                ),
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
                schedule_text_builder=lambda cfg: (
                    f"每周 {cfg.cron_day_of_week} {cfg.cron_hour:02d}:{cfg.cron_minute:02d}"
                ),
            ),
            "batch_download": _JobMeta(
                job_id="batch_download",
                name="下载自选日 K",
                description="批量下载自选池日线到本地数据库",
                runner=self._run_batch_download,
                config_attr="batch_download",
                schedule_builder=lambda cfg: CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=cfg.cron_hour,
                    minute=cfg.cron_minute,
                ),
                schedule_text_builder=lambda cfg: (
                    f"工作日 {cfg.cron_hour:02d}:{cfg.cron_minute:02d}，"
                    f"起始于 {cfg.download_start}"
                ),
            ),
            "screen_intraday": _JobMeta(
                job_id="screen_intraday",
                name="盘中自动选股",
                description="交易时段多维度选股（动量+换手），结果写入选股历史",
                runner=lambda: run_scheduled_auto_screen("screen_intraday"),
                config_attr="screen_intraday",
                schedule_builder=lambda _cfg: CronTrigger(hour="10,14", minute=0),
                schedule_text_builder=lambda cfg: (
                    f"交易日 {cfg.cron_hours}:{cfg.cron_minute_intraday:02d} · "
                    f"配方 {cfg.recipe_id or 'intraday_multi'}"
                ),
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
                schedule_text_builder=lambda cfg: (
                    f"工作日 {cfg.cron_hour:02d}:{cfg.cron_minute:02d} · "
                    f"配方 {cfg.recipe_id or 'post_close_multi'}"
                ),
            ),
        }
        self._scheduler.add_listener(self._on_job_max_instances, EVENT_JOB_MAX_INSTANCES)
        self._refresh_status_cache()

    def _collect_quotes_interval(self) -> int:
        cfg = self._get_job_config(_COLLECT_QUOTES_JOB_ID)
        return max(cfg.interval_seconds, _COLLECT_QUOTES_INTERVAL_MIN)

    def _run_collect_quotes(self, *, force: bool = False) -> JobResult:
        now = datetime.now(_SHANGHAI_TZ)
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
        if force and not is_ashare_trading_session(now):
            return JobResult(
                success=result.success,
                skipped=False,
                message=f"非交易时段手动采集 · {result.message}",
            )
        return result

    def _next_collect_quotes_run_at(self, *, prefer_immediate: bool = False) -> datetime:
        now = datetime.now(_SHANGHAI_TZ)
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

    def _notify(self, job_id: str) -> None:
        for callback in list(self._listeners):
            try:
                callback(job_id)
            except Exception:
                pass

    def _run_batch_download(self) -> JobResult:
        cfg = self._config.batch_download
        start = datetime.strptime(cfg.download_start, "%Y-%m-%d")
        return batch_download_watchlist(start=start, end=datetime.now())

    def _get_job_config(self, job_id: str) -> JobConfig:
        meta = self._jobs[job_id]
        return getattr(self._config, meta.config_attr)

    def _set_job_config(self, job_id: str, job_config: JobConfig) -> None:
        meta = self._jobs[job_id]
        setattr(self._config, meta.config_attr, job_config)

    def _refresh_status_cache(self) -> None:
        for job_id, meta in self._jobs.items():
            cfg = self._get_job_config(job_id)
            next_run = None
            if self._scheduler.running:
                job = self._scheduler.get_job(job_id)
                if job and job.next_run_time:
                    next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")

            previous = self._status.get(job_id)
            self._status[job_id] = JobStatus(
                job_id=job_id,
                name=meta.name,
                description=meta.description,
                schedule_text=meta.schedule_text_builder(cfg),
                enabled=cfg.enabled,
                running=job_id in self._running_jobs,
                last_run_at=previous.last_run_at if previous else None,
                last_message=previous.last_message if previous else None,
                last_success=previous.last_success if previous else None,
                next_run_at=next_run,
            )

    def get_config(self) -> SchedulerConfig:
        return self._config

    def get_job_config(self, job_id: str) -> JobConfig:
        return self._get_job_config(job_id)

    def save_config(self) -> None:
        save_scheduler_config(self._config)

    def list_status(self) -> list[JobStatus]:
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
        self._refresh_status_cache()
        return self._status.get(job_id)

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
                hours = [h.strip() for h in cfg.cron_hours.split(",") if h.strip()]
                trigger = CronTrigger(
                    day_of_week=cfg.cron_day_of_week,
                    hour=hours or "10,14",
                    minute=cfg.cron_minute_intraday,
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
        cfg = self._get_job_config(job_id)
        cfg.enabled = enabled
        self.save_config()
        self.reload_jobs()

    def update_job_config(self, job_id: str, **kwargs: Any) -> None:
        cfg = self._get_job_config(job_id)
        for key, value in kwargs.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        self.save_config()
        self.reload_jobs()

    def run_now(self, job_id: str) -> bool:
        if job_id not in self._jobs:
            return False
        if job_id in self._running_jobs:
            return False
        force = job_id in (
            _COLLECT_QUOTES_JOB_ID,
            "screen_intraday",
            "screen_post_close",
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

        skipped = False
        try:
            if job_id == _COLLECT_QUOTES_JOB_ID:
                result = self._run_collect_quotes(force=force)
            elif job_id in ("screen_intraday", "screen_post_close"):
                result = run_scheduled_auto_screen(job_id, force=force)
            else:
                result = meta.runner()
            message = result.message
            skipped = result.skipped
            success = result.success if not skipped else True
        except Exception as ex:
            message = str(ex)
            success = False

        finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = self._status.get(job_id)
        if status:
            status.last_run_at = finished_at
            status.last_message = message
            status.last_success = None if skipped else success
            status.running = False

        self._run_log.append(
            JobRunRecord(
                finished_at=finished_at,
                job_id=job_id,
                job_name=meta.name,
                success=success,
                message=message,
                skipped=skipped,
            )
        )

        with self._lock:
            self._running_jobs.discard(job_id)

        self._refresh_status_cache()
        self._notify(job_id)

        if job_id == _COLLECT_QUOTES_JOB_ID and self._get_job_config(job_id).enabled:
            self._schedule_collect_quotes()
