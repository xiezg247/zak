"""后台任务目录：CLI 与调度器共用的任务元数据。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_ashare.jobs.feed.sync_bilibili import BILIBILI_SYNC_INTERVAL_SECONDS

COLLECT_QUOTES_JOB_ID = "collect_quotes"
COLLECT_QUOTES_INTERVAL_SECONDS = 5

MANUAL_FORCE_JOB_IDS = frozenset(
    {
        COLLECT_QUOTES_JOB_ID,
        "screen_intraday",
        "screen_post_close",
        "scan_horizon_outlook",
        "warm_watchlist_strategy_cache",
        "warm_radar_card_snapshots",
        "sync_bilibili_feed",
    },
)


@dataclass(frozen=True, slots=True)
class JobSpec:
    """任务元数据（名称与说明为调度器主文案）。"""

    job_id: str
    name: str
    description: str
    config_attr: str
    cli_description: str | None = None

    @property
    def cli_text(self) -> str:
        return self.cli_description or self.description


JOB_SPECS: tuple[JobSpec, ...] = (
    JobSpec(
        job_id=COLLECT_QUOTES_JOB_ID,
        name="行情采集",
        description="TickFlow 全市场快照写入 Redis（开发调试用，生产建议独立进程）",
        cli_description="TickFlow 全市场快照写入 Redis",
        config_attr="collect_quotes",
    ),
    JobSpec(
        job_id="sync_universe",
        name="同步 A 股列表",
        description="从 TickFlow 更新全市场标的到本地 SQLite",
        config_attr="sync_universe",
    ),
    JobSpec(
        job_id="sync_stock_industry",
        name="同步行业映射",
        description="从 Tushare 申万 2021 L2 拉取行业分类，失败时回退 stock_basic",
        cli_description="从 Tushare 申万 2021 L2 更新行业分类本地缓存（失败回退 stock_basic）",
        config_attr="sync_stock_industry",
    ),
    JobSpec(
        job_id="sync_trade_calendar",
        name="同步交易日历",
        description="从 Tushare 更新 A 股交易日历到本地 SQLite",
        config_attr="sync_trade_calendar",
    ),
    JobSpec(
        job_id="batch_download_universe",
        name="全市场日 K",
        description="从 Tushare 为全 A 股下载/补全自 2020 年以来的日 K；增量由「补全本地日 K」维护",
        cli_description="从 Tushare 为全 A 股下载/补全自 2020 年以来的日 K",
        config_attr="batch_download_universe",
    ),
    JobSpec(
        job_id="prefetch_moneyflow",
        name="主力资金预拉",
        description="收盘后从 Tushare 拉取全市场 moneyflow 主力资金流向，供雷达与个股分析",
        cli_description="收盘后拉取全市场 moneyflow 主力资金流向到本地缓存",
        config_attr="prefetch_moneyflow",
    ),
    JobSpec(
        job_id="sync_sector_flow_daily",
        name="板块资金同步",
        description="收盘后拉取东财行业/同花顺概念近 N 日板块资金流，写入 sector_flow_daily 供详情页近5日柱图",
        cli_description="收盘后拉取东财行业/同花顺概念板块资金流近 N 日到本地",
        config_attr="sync_sector_flow_daily",
    ),
    JobSpec(
        job_id="sync_suspend_daily",
        name="停牌日同步",
        description="收盘后从 Tushare 增量拉取最近交易日全市场停牌记录，供日 K 断层扫描排除",
        cli_description="收盘后增量拉取最近交易日全市场停牌记录",
        config_attr="sync_suspend_daily",
    ),
    JobSpec(
        job_id="prefetch_tushare",
        name="Tushare 因子预拉",
        description="收盘后拉取 daily_basic、涨跌停、指数、北向、stock_basic 等写入本地缓存",
        cli_description="收盘后拉取 daily_basic、涨跌停、指数、北向等写入本地缓存",
        config_attr="prefetch_tushare",
    ),
    JobSpec(
        job_id="prefetch_concept_board",
        name="概念板块预拉",
        description="预热同花顺概念指数、当日行情与强势概念成分映射（雷达概念维度依赖）",
        cli_description="预热同花顺概念指数、行情与强势概念成分映射",
        config_attr="prefetch_concept_board",
    ),
    JobSpec(
        job_id="warm_market_summary",
        name="市场摘要预热",
        description="收盘后计算情绪周期并写入内存缓存，供 UI / 风控只读（避免启动阻塞）",
        cli_description="计算情绪周期并写入内存缓存",
        config_attr="warm_market_summary",
    ),
    JobSpec(
        job_id="warm_watchlist_strategy_cache",
        name="策略信号磁盘预热",
        description="收盘后为信号区/持仓区名单重算策略快照并写入磁盘 cache，供 UI hydrate",
        cli_description="为信号区/持仓区名单重算策略快照并写入磁盘 cache",
        config_attr="warm_watchlist_strategy_cache",
    ),
    JobSpec(
        job_id="sync_watchlist_financials",
        name="同步自选财报",
        description="增量拉取自选池利润表/资产负债表/现金流量表/财务指标到本地",
        cli_description="增量拉取自选池三表与财务指标到本地",
        config_attr="sync_watchlist_financials",
    ),
    JobSpec(
        job_id="sync_disclosure_calendar",
        name="同步披露计划",
        description="拉取自选池财报预约披露日期，用于驱动财报增量同步",
        cli_description="拉取自选池财报预约披露日期",
        config_attr="sync_disclosure_calendar",
    ),
    JobSpec(
        job_id="batch_fill_stale",
        name="补全本地日 K",
        description="为本地已下载列表中过期的日 K 增量补全到最近交易日",
        cli_description="为本地已下载列表中过期的日 K 增量补全",
        config_attr="batch_fill_stale",
    ),
    JobSpec(
        job_id="fill_focus_pool_minute",
        name="关注池 1m K 补全",
        description="为信号区与持仓记账标的补全/增量 1 分钟 K 线",
        cli_description="为信号区 + 持仓补全/增量 1 分钟 K 线",
        config_attr="fill_focus_pool_minute",
    ),
    JobSpec(
        job_id="screen_intraday",
        name="盘中自动选股",
        description="交易时段多维度选股（动量+换手），结果写入选股历史",
        cli_description="交易时段多维度选股，结果写入选股历史",
        config_attr="screen_intraday",
    ),
    JobSpec(
        job_id="screen_post_close",
        name="盘后自动选股",
        description="收盘后多维度选股（资金+估值+动量），结果写入选股历史",
        config_attr="screen_post_close",
    ),
    JobSpec(
        job_id="scan_horizon_outlook",
        name="雷达展望扫描",
        description="收盘后全市场扫描未来·关注/可持/情景/预测，写入本地缓存",
        cli_description="全市场扫描未来·关注/可持并写入本地缓存",
        config_attr="scan_horizon_outlook",
    ),
    JobSpec(
        job_id="warm_radar_card_snapshots",
        name="雷达卡片预热",
        description="交易时段批量重算雷达统计/发现重卡并写入本地快照，供 UI 冷读",
        cli_description="重算雷达统计/发现卡片并写入本地快照",
        config_attr="warm_radar_card_snapshots",
    ),
    JobSpec(
        job_id="sync_bilibili_feed",
        name="B站订阅同步",
        description="拉取已订阅 UP 主的最新视频与动态，写入信息流",
        cli_description="拉取已订阅 UP 主视频与动态写入信息流",
        config_attr="sync_bilibili_feed",
    ),
)

JOBS_BY_ID: dict[str, JobSpec] = {spec.job_id: spec for spec in JOB_SPECS}

JOB_CATALOG: dict[str, tuple[str, str]] = {spec.job_id: (spec.name, spec.cli_text) for spec in JOB_SPECS}

__all__ = [
    "BILIBILI_SYNC_INTERVAL_SECONDS",
    "COLLECT_QUOTES_INTERVAL_SECONDS",
    "COLLECT_QUOTES_JOB_ID",
    "JOB_CATALOG",
    "JOBS_BY_ID",
    "JOB_SPECS",
    "MANUAL_FORCE_JOB_IDS",
    "JobSpec",
]
