"""定时任务配置持久化。"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from vnpy_common.domain.base import MutableModel
from vnpy_common.paths import APP_ID, VNTRADER_DIR

SCHEDULER_CONFIG_PATH = VNTRADER_DIR / f"{APP_ID}_scheduler.json"

# 推荐调度时刻：按依赖顺序排列；全市场日 K 约 30 分钟，后续任务从 17:00 起排。
# (hour, minute, day_of_week)；day_of_week 省略时默认为 mon-fri。
_WEEKLY_CRON: dict[str, tuple[int, int, str]] = {
    "sync_trade_calendar": (7, 50, "mon"),
    "sync_universe": (8, 0, "mon"),
    "sync_stock_industry": (8, 15, "mon"),
}
_POST_CLOSE_CRON: dict[str, tuple[int, int]] = {
    "batch_download_universe": (16, 20),
    "prefetch_moneyflow": (17, 0),
    "prefetch_tushare": (17, 10),
    "sync_suspend_daily": (17, 20),
    "prefetch_concept_board": (17, 30),
    "warm_market_summary": (17, 40),
    "sync_sector_flow_daily": (17, 45),
    "sync_disclosure_calendar": (17, 50),
    "screen_post_close": (18, 0),
    "scan_horizon_outlook": (18, 15),
    "sync_watchlist_financials": (18, 20),
    "batch_fill_stale": (18, 30),
    "warm_watchlist_strategy_cache": (18, 45),
    "fill_focus_pool_minute": (19, 0),
}


def _job_config_from_cron(
    hour: int,
    minute: int,
    day_of_week: str = "mon-fri",
    *,
    enabled: bool = False,
    download_start: str = "2020-01-01",
) -> JobConfig:
    return JobConfig(
        enabled=enabled,
        cron_hour=hour,
        cron_minute=minute,
        cron_day_of_week=day_of_week,
        download_start=download_start,
    )


def _auto_screen_from_cron(
    hour: int,
    minute: int,
    day_of_week: str = "mon-fri",
    *,
    enabled: bool = False,
    recipe_id: str = "",
    top_n: int = 20,
) -> AutoScreenJobConfig:
    return AutoScreenJobConfig(
        enabled=enabled,
        recipe_id=recipe_id,
        top_n=top_n,
        cron_hour=hour,
        cron_minute=minute,
        cron_day_of_week=day_of_week,
    )


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
    cron_hour: int = Field(default=18, description="Cron 小时（收盘后）")
    cron_minute: int = Field(default=0, description="Cron 分钟")
    cron_day_of_week: str = Field(default="mon-fri", description="Cron 星期")
    cron_hours: str = Field(default="10,14", description="盘中 Cron 小时列表")
    cron_minute_intraday: int = Field(default=2, description="盘中 Cron 分钟")


class SchedulerConfig(MutableModel):
    collect_quotes: JobConfig = Field(
        default_factory=lambda: JobConfig(enabled=False, interval_seconds=30),
        description="行情采集任务配置",
    )
    sync_universe: JobConfig = Field(
        default_factory=lambda: _job_config_from_cron(
            *_WEEKLY_CRON["sync_universe"],
            enabled=False,
        ),
        description="同步 A 股列表任务配置",
    )
    sync_stock_industry: JobConfig = Field(
        default_factory=lambda: _job_config_from_cron(
            *_WEEKLY_CRON["sync_stock_industry"],
            enabled=True,
        ),
        description="同步行业分类任务配置",
    )
    sync_trade_calendar: JobConfig = Field(
        default_factory=lambda: _job_config_from_cron(
            *_WEEKLY_CRON["sync_trade_calendar"],
            enabled=False,
        ),
        description="同步交易日历任务配置",
    )
    batch_download_universe: JobConfig = Field(
        default_factory=lambda: _job_config_from_cron(
            *_POST_CLOSE_CRON["batch_download_universe"],
            enabled=False,
        ),
        description="全市场日 K 批量下载配置",
    )
    prefetch_moneyflow: JobConfig = Field(
        default_factory=lambda: _job_config_from_cron(*_POST_CLOSE_CRON["prefetch_moneyflow"]),
        description="预取资金流任务配置",
    )
    sync_sector_flow_daily: JobConfig = Field(
        default_factory=lambda: _job_config_from_cron(*_POST_CLOSE_CRON["sync_sector_flow_daily"]),
        description="同步板块日终资金流配置",
    )
    sync_suspend_daily: JobConfig = Field(
        default_factory=lambda: _job_config_from_cron(*_POST_CLOSE_CRON["sync_suspend_daily"]),
        description="同步停复牌任务配置",
    )
    prefetch_tushare: JobConfig = Field(
        default_factory=lambda: _job_config_from_cron(*_POST_CLOSE_CRON["prefetch_tushare"]),
        description="预取 Tushare 因子任务配置",
    )
    prefetch_concept_board: JobConfig = Field(
        default_factory=lambda: _job_config_from_cron(*_POST_CLOSE_CRON["prefetch_concept_board"]),
        description="预取概念板块任务配置",
    )
    warm_market_summary: JobConfig = Field(
        default_factory=lambda: _job_config_from_cron(*_POST_CLOSE_CRON["warm_market_summary"]),
        description="预热市场摘要任务配置",
    )
    warm_watchlist_strategy_cache: JobConfig = Field(
        default_factory=lambda: _job_config_from_cron(*_POST_CLOSE_CRON["warm_watchlist_strategy_cache"]),
        description="策略信号磁盘预热任务配置",
    )
    sync_watchlist_financials: JobConfig = Field(
        default_factory=lambda: _job_config_from_cron(
            *_POST_CLOSE_CRON["sync_watchlist_financials"],
            enabled=True,
        ),
        description="同步自选财报任务配置",
    )
    sync_disclosure_calendar: JobConfig = Field(
        default_factory=lambda: _job_config_from_cron(
            *_POST_CLOSE_CRON["sync_disclosure_calendar"],
            enabled=True,
        ),
        description="同步披露日历任务配置",
    )
    batch_fill_stale: JobConfig = Field(
        default_factory=lambda: _job_config_from_cron(*_POST_CLOSE_CRON["batch_fill_stale"]),
        description="批量补全过期日 K 配置",
    )
    fill_focus_pool_minute: JobConfig = Field(
        default_factory=lambda: _job_config_from_cron(
            *_POST_CLOSE_CRON["fill_focus_pool_minute"],
            enabled=True,
        ),
        description="关注池 1m K 补全配置",
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
        default_factory=lambda: _auto_screen_from_cron(
            *_POST_CLOSE_CRON["screen_post_close"],
            enabled=False,
            recipe_id="post_close_multi",
        ),
        description="收盘后自动选股配置",
    )
    scan_horizon_outlook: JobConfig = Field(
        default_factory=lambda: _job_config_from_cron(*_POST_CLOSE_CRON["scan_horizon_outlook"]),
        description="雷达展望扫描任务配置",
    )
    sync_bilibili_feed: JobConfig = Field(
        default_factory=lambda: JobConfig(
            enabled=True,
            interval_seconds=300,
            cron_hour=8,
            cron_minute=0,
            cron_day_of_week="mon-sun",
        ),
        description="B站订阅同步任务配置",
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
            "warm_watchlist_strategy_cache": dump_job(self.warm_watchlist_strategy_cache),
            "sync_watchlist_financials": dump_job(self.sync_watchlist_financials),
            "sync_disclosure_calendar": dump_job(self.sync_disclosure_calendar),
            "batch_fill_stale": dump_job(self.batch_fill_stale),
            "fill_focus_pool_minute": dump_job(self.fill_focus_pool_minute),
            "screen_intraday": dump_auto(self.screen_intraday),
            "screen_post_close": dump_auto(self.screen_post_close),
            "scan_horizon_outlook": dump_job(self.scan_horizon_outlook),
            "sync_bilibili_feed": dump_job(self.sync_bilibili_feed),
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
            warm_watchlist_strategy_cache=load_job(
                "warm_watchlist_strategy_cache",
                defaults.warm_watchlist_strategy_cache,
            ),
            sync_watchlist_financials=load_job("sync_watchlist_financials", defaults.sync_watchlist_financials),
            sync_disclosure_calendar=load_job("sync_disclosure_calendar", defaults.sync_disclosure_calendar),
            batch_fill_stale=load_job("batch_fill_stale", defaults.batch_fill_stale),
            fill_focus_pool_minute=load_job("fill_focus_pool_minute", defaults.fill_focus_pool_minute),
            screen_intraday=load_auto("screen_intraday", defaults.screen_intraday),
            screen_post_close=load_auto("screen_post_close", defaults.screen_post_close),
            scan_horizon_outlook=load_job("scan_horizon_outlook", defaults.scan_horizon_outlook),
            sync_bilibili_feed=load_job("sync_bilibili_feed", defaults.sync_bilibili_feed),
        )


def load_scheduler_config(path: Path | None = None) -> SchedulerConfig:
    if path is not None:
        if not path.exists():
            return SchedulerConfig()
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return SchedulerConfig()
        return SchedulerConfig.from_dict(data)

    from vnpy_ashare.storage.system.scheduler_config_store import load_scheduler_config_dict

    stored = load_scheduler_config_dict()
    if stored is not None:
        return SchedulerConfig.from_dict(stored)

    if not SCHEDULER_CONFIG_PATH.exists():
        return SchedulerConfig()
    try:
        with SCHEDULER_CONFIG_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return SchedulerConfig()
    config = SchedulerConfig.from_dict(data)
    save_scheduler_config(config)
    return config


def save_scheduler_config(config: SchedulerConfig, path: Path | None = None) -> Path:
    if path is not None:
        target = path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
        return target

    from vnpy_ashare.storage.system.scheduler_config_store import save_scheduler_config_dict

    save_scheduler_config_dict(config.to_dict())
    return SCHEDULER_CONFIG_PATH
