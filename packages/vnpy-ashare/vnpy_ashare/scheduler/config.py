"""定时任务配置持久化。"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from vnpy_common.domain.base import MutableModel
from vnpy_common.paths import APP_ID, VNTRADER_DIR

SCHEDULER_CONFIG_PATH = VNTRADER_DIR / f"{APP_ID}_scheduler.json"


class JobConfig(MutableModel):
    enabled: bool = Field(default=False, description="是否启用")
    interval_seconds: int = Field(default=30, description="间隔触发秒数")
    cron_hour: int = Field(default=8, description="Cron 小时")
    cron_minute: int = Field(default=0, description="Cron 分钟")
    cron_day_of_week: str = Field(default="mon", description="Cron 星期")
    download_start: str = Field(default="2020-01-01", description="批量下载起始日")


class AutoScreenJobConfig(MutableModel):
    enabled: bool = Field(default=False, description="是否启用")
    recipe_id: str = Field(default="", description="配方 ID")
    top_n: int = Field(default=20, description="输出 Top N")
    cron_hour: int = Field(default=16, description="Cron 小时（收盘后）")
    cron_minute: int = Field(default=35, description="Cron 分钟")
    cron_day_of_week: str = Field(default="mon-fri", description="Cron 星期")
    cron_hours: str = Field(default="10,14", description="盘中 Cron 小时列表")
    cron_minute_intraday: int = Field(default=2, description="盘中 Cron 分钟")


class SchedulerConfig(MutableModel):
    collect_quotes: JobConfig = Field(
        default_factory=lambda: JobConfig(enabled=False, interval_seconds=30),
        description="行情采集任务配置",
    )
    sync_universe: JobConfig = Field(
        default_factory=lambda: JobConfig(
            enabled=False,
            cron_hour=8,
            cron_minute=0,
            cron_day_of_week="mon",
        ),
        description="同步 A 股列表任务配置",
    )
    sync_stock_industry: JobConfig = Field(
        default_factory=lambda: JobConfig(
            enabled=True,
            cron_hour=8,
            cron_minute=10,
            cron_day_of_week="mon",
        ),
        description="同步行业分类任务配置",
    )
    sync_trade_calendar: JobConfig = Field(
        default_factory=lambda: JobConfig(
            enabled=False,
            cron_hour=7,
            cron_minute=50,
            cron_day_of_week="mon",
        ),
        description="同步交易日历任务配置",
    )
    batch_download_universe: JobConfig = Field(
        default_factory=lambda: JobConfig(
            enabled=False,
            cron_hour=16,
            cron_minute=25,
            cron_day_of_week="mon-fri",
            download_start="2020-01-01",
        ),
        description="全市场日 K 批量下载配置",
    )
    prefetch_moneyflow: JobConfig = Field(
        default_factory=lambda: JobConfig(
            enabled=False,
            cron_hour=16,
            cron_minute=31,
            cron_day_of_week="mon-fri",
        ),
        description="预取资金流任务配置",
    )
    sync_sector_flow_daily: JobConfig = Field(
        default_factory=lambda: JobConfig(
            enabled=False,
            cron_hour=16,
            cron_minute=36,
            cron_day_of_week="mon-fri",
        ),
        description="同步板块日终资金流配置",
    )
    sync_suspend_daily: JobConfig = Field(
        default_factory=lambda: JobConfig(
            enabled=False,
            cron_hour=16,
            cron_minute=33,
            cron_day_of_week="mon-fri",
        ),
        description="同步停复牌任务配置",
    )
    prefetch_tushare: JobConfig = Field(
        default_factory=lambda: JobConfig(
            enabled=False,
            cron_hour=16,
            cron_minute=32,
            cron_day_of_week="mon-fri",
        ),
        description="预取 Tushare 因子任务配置",
    )
    prefetch_concept_board: JobConfig = Field(
        default_factory=lambda: JobConfig(
            enabled=False,
            cron_hour=16,
            cron_minute=33,
            cron_day_of_week="mon-fri",
        ),
        description="预取概念板块任务配置",
    )
    warm_market_summary: JobConfig = Field(
        default_factory=lambda: JobConfig(
            enabled=False,
            cron_hour=16,
            cron_minute=34,
            cron_day_of_week="mon-fri",
        ),
        description="预热市场摘要任务配置",
    )
    sync_watchlist_financials: JobConfig = Field(
        default_factory=lambda: JobConfig(
            enabled=True,
            cron_hour=16,
            cron_minute=45,
            cron_day_of_week="mon-fri",
        ),
        description="同步自选财报任务配置",
    )
    sync_disclosure_calendar: JobConfig = Field(
        default_factory=lambda: JobConfig(
            enabled=True,
            cron_hour=16,
            cron_minute=40,
            cron_day_of_week="mon-fri",
        ),
        description="同步披露日历任务配置",
    )
    batch_fill_stale: JobConfig = Field(
        default_factory=lambda: JobConfig(
            enabled=False,
            cron_hour=17,
            cron_minute=0,
            cron_day_of_week="mon-fri",
        ),
        description="批量补全过期日 K 配置",
    )
    screen_intraday: AutoScreenJobConfig = Field(
        default_factory=lambda: AutoScreenJobConfig(
            enabled=False,
            recipe_id="intraday_multi",
            cron_hours="10,14",
            cron_minute_intraday=2,
        ),
        description="盘中自动选股配置",
    )
    screen_post_close: AutoScreenJobConfig = Field(
        default_factory=lambda: AutoScreenJobConfig(
            enabled=False,
            recipe_id="post_close_multi",
            cron_hour=16,
            cron_minute=35,
        ),
        description="收盘后自动选股配置",
    )
    scan_horizon_outlook: JobConfig = Field(
        default_factory=lambda: JobConfig(
            enabled=False,
            cron_hour=16,
            cron_minute=40,
            cron_day_of_week="mon-fri",
        ),
        description="雷达展望扫描任务配置",
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
            "sync_stock_industry": dump_job(self.sync_stock_industry),
            "sync_trade_calendar": dump_job(self.sync_trade_calendar),
            "batch_download_universe": dump_job(self.batch_download_universe),
            "prefetch_moneyflow": dump_job(self.prefetch_moneyflow),
            "sync_sector_flow_daily": dump_job(self.sync_sector_flow_daily),
            "sync_suspend_daily": dump_job(self.sync_suspend_daily),
            "prefetch_tushare": dump_job(self.prefetch_tushare),
            "prefetch_concept_board": dump_job(self.prefetch_concept_board),
            "warm_market_summary": dump_job(self.warm_market_summary),
            "sync_watchlist_financials": dump_job(self.sync_watchlist_financials),
            "sync_disclosure_calendar": dump_job(self.sync_disclosure_calendar),
            "batch_fill_stale": dump_job(self.batch_fill_stale),
            "screen_intraday": dump_auto(self.screen_intraday),
            "screen_post_close": dump_auto(self.screen_post_close),
            "scan_horizon_outlook": dump_job(self.scan_horizon_outlook),
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
            sync_stock_industry=load_job("sync_stock_industry", defaults.sync_stock_industry),
            sync_trade_calendar=load_job("sync_trade_calendar", defaults.sync_trade_calendar),
            batch_download_universe=load_job("batch_download_universe", defaults.batch_download_universe),
            prefetch_moneyflow=load_job("prefetch_moneyflow", defaults.prefetch_moneyflow),
            sync_sector_flow_daily=load_job("sync_sector_flow_daily", defaults.sync_sector_flow_daily),
            sync_suspend_daily=load_job("sync_suspend_daily", defaults.sync_suspend_daily),
            prefetch_tushare=load_job("prefetch_tushare", defaults.prefetch_tushare),
            prefetch_concept_board=load_job("prefetch_concept_board", defaults.prefetch_concept_board),
            warm_market_summary=load_job("warm_market_summary", defaults.warm_market_summary),
            sync_watchlist_financials=load_job("sync_watchlist_financials", defaults.sync_watchlist_financials),
            sync_disclosure_calendar=load_job("sync_disclosure_calendar", defaults.sync_disclosure_calendar),
            batch_fill_stale=load_job("batch_fill_stale", defaults.batch_fill_stale),
            screen_intraday=load_auto("screen_intraday", defaults.screen_intraday),
            screen_post_close=load_auto("screen_post_close", defaults.screen_post_close),
            scan_horizon_outlook=load_job("scan_horizon_outlook", defaults.scan_horizon_outlook),
        )


def _migrate_scheduler_data(data: dict) -> tuple[dict, bool]:
    """将旧 ``batch_download`` 键合并进 ``batch_download_universe`` 并移除旧键。"""
    legacy = data.get("batch_download")
    if not isinstance(legacy, dict):
        return data, False
    migrated = {key: value for key, value in data.items() if key != "batch_download"}
    universe_raw = dict(migrated.get("batch_download_universe") or {})
    legacy_start = legacy.get("download_start")
    if legacy_start and not universe_raw.get("download_start"):
        universe_raw["download_start"] = str(legacy_start)
    migrated["batch_download_universe"] = universe_raw
    return migrated, True


def load_scheduler_config(path: Path | None = None) -> SchedulerConfig:
    target = path or SCHEDULER_CONFIG_PATH
    if not target.exists():
        return SchedulerConfig()
    try:
        with target.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return SchedulerConfig()
    migrated, changed = _migrate_scheduler_data(data)
    config = SchedulerConfig.from_dict(migrated)
    if changed:
        save_scheduler_config(config, target)
    return config


def save_scheduler_config(config: SchedulerConfig, path: Path | None = None) -> Path:
    target = path or SCHEDULER_CONFIG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
    return target
