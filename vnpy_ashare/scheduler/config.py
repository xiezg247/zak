"""定时任务配置持久化。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from vnpy_ashare.paths import APP_ID, VNTRADER_DIR

SCHEDULER_CONFIG_PATH = VNTRADER_DIR / f"{APP_ID}_scheduler.json"


@dataclass
class JobConfig:
    enabled: bool = False
    interval_seconds: int = 30
    cron_hour: int = 8
    cron_minute: int = 0
    cron_day_of_week: str = "mon"
    download_start: str = "2020-01-01"


@dataclass
class AutoScreenJobConfig:
    enabled: bool = False
    recipe_id: str = ""
    top_n: int = 20
    cron_hour: int = 16
    cron_minute: int = 35
    cron_day_of_week: str = "mon-fri"
    cron_hours: str = "10,14"
    cron_minute_intraday: int = 0


@dataclass
class SchedulerConfig:
    collect_quotes: JobConfig = field(default_factory=lambda: JobConfig(enabled=False, interval_seconds=30))
    sync_universe: JobConfig = field(
        default_factory=lambda: JobConfig(
            enabled=False,
            cron_hour=8,
            cron_minute=0,
            cron_day_of_week="mon",
        )
    )
    batch_download: JobConfig = field(
        default_factory=lambda: JobConfig(
            enabled=False,
            cron_hour=16,
            cron_minute=30,
            cron_day_of_week="mon-fri",
            download_start="2020-01-01",
        )
    )
    screen_intraday: AutoScreenJobConfig = field(
        default_factory=lambda: AutoScreenJobConfig(
            enabled=False,
            recipe_id="intraday_multi",
            cron_hours="10,14",
        )
    )
    screen_post_close: AutoScreenJobConfig = field(
        default_factory=lambda: AutoScreenJobConfig(
            enabled=False,
            recipe_id="post_close_multi",
            cron_hour=16,
            cron_minute=35,
        )
    )

    def to_dict(self) -> dict:
        def dump_job(job: JobConfig) -> dict:
            return {
                "enabled": job.enabled,
                "interval_seconds": job.interval_seconds,
                "cron_hour": job.cron_hour,
                "cron_minute": job.cron_minute,
                "cron_day_of_week": job.cron_day_of_week,
                "download_start": job.download_start,
            }

        def dump_auto(job: AutoScreenJobConfig) -> dict:
            return {
                "enabled": job.enabled,
                "recipe_id": job.recipe_id,
                "top_n": job.top_n,
                "cron_hour": job.cron_hour,
                "cron_minute": job.cron_minute,
                "cron_day_of_week": job.cron_day_of_week,
                "cron_hours": job.cron_hours,
                "cron_minute_intraday": job.cron_minute_intraday,
            }

        return {
            "collect_quotes": dump_job(self.collect_quotes),
            "sync_universe": dump_job(self.sync_universe),
            "batch_download": dump_job(self.batch_download),
            "screen_intraday": dump_auto(self.screen_intraday),
            "screen_post_close": dump_auto(self.screen_post_close),
        }

    @classmethod
    def from_dict(cls, data: dict) -> SchedulerConfig:
        def load_job(key: str, defaults: JobConfig) -> JobConfig:
            raw = data.get(key, {})
            return JobConfig(
                enabled=bool(raw.get("enabled", defaults.enabled)),
                interval_seconds=int(raw.get("interval_seconds", defaults.interval_seconds)),
                cron_hour=int(raw.get("cron_hour", defaults.cron_hour)),
                cron_minute=int(raw.get("cron_minute", defaults.cron_minute)),
                cron_day_of_week=str(raw.get("cron_day_of_week", defaults.cron_day_of_week)),
                download_start=str(raw.get("download_start", defaults.download_start)),
            )

        def load_auto(key: str, defaults: AutoScreenJobConfig) -> AutoScreenJobConfig:
            raw = data.get(key, {})
            return AutoScreenJobConfig(
                enabled=bool(raw.get("enabled", defaults.enabled)),
                recipe_id=str(raw.get("recipe_id", defaults.recipe_id)),
                top_n=int(raw.get("top_n", defaults.top_n)),
                cron_hour=int(raw.get("cron_hour", defaults.cron_hour)),
                cron_minute=int(raw.get("cron_minute", defaults.cron_minute)),
                cron_day_of_week=str(raw.get("cron_day_of_week", defaults.cron_day_of_week)),
                cron_hours=str(raw.get("cron_hours", defaults.cron_hours)),
                cron_minute_intraday=int(raw.get("cron_minute_intraday", defaults.cron_minute_intraday)),
            )

        defaults = cls()
        return cls(
            collect_quotes=load_job("collect_quotes", defaults.collect_quotes),
            sync_universe=load_job("sync_universe", defaults.sync_universe),
            batch_download=load_job("batch_download", defaults.batch_download),
            screen_intraday=load_auto("screen_intraday", defaults.screen_intraday),
            screen_post_close=load_auto("screen_post_close", defaults.screen_post_close),
        )


def load_scheduler_config(path: Path | None = None) -> SchedulerConfig:
    target = path or SCHEDULER_CONFIG_PATH
    if not target.exists():
        return SchedulerConfig()
    try:
        with target.open(encoding="utf-8") as f:
            return SchedulerConfig.from_dict(json.load(f))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return SchedulerConfig()


def save_scheduler_config(config: SchedulerConfig, path: Path | None = None) -> Path:
    target = path or SCHEDULER_CONFIG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
    return target
