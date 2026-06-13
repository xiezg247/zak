"""雷达页卡片注册表（选股 / 发现 / 自选 / 板块 / 展望）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RadarCategory = Literal["screen", "discovery", "watchlist", "sector", "outlook"]

RADAR_GRID_COLUMNS = 3

# 盘中敏感卡默认自动刷新间隔（展望/选股仅手动或读缓存）
RADAR_REFRESH_OFF_MS = 0
RADAR_DISCOVERY_AUTO_REFRESH_MS = 60_000
RADAR_WATCHLIST_AUTO_REFRESH_MS = 60_000
RADAR_SECTOR_AUTO_REFRESH_MS = 180_000


@dataclass(frozen=True)
class RadarRefreshOption:
    ms: int
    label: str


RADAR_DISCOVERY_REFRESH_OPTIONS: tuple[RadarRefreshOption, ...] = (
    RadarRefreshOption(RADAR_REFRESH_OFF_MS, "不刷新"),
    RadarRefreshOption(30_000, "30 秒"),
    RadarRefreshOption(60_000, "1 分钟"),
    RadarRefreshOption(120_000, "2 分钟"),
)

RADAR_WATCHLIST_REFRESH_OPTIONS: tuple[RadarRefreshOption, ...] = RADAR_DISCOVERY_REFRESH_OPTIONS

RADAR_SECTOR_REFRESH_OPTIONS: tuple[RadarRefreshOption, ...] = (
    RadarRefreshOption(RADAR_REFRESH_OFF_MS, "不刷新"),
    RadarRefreshOption(60_000, "1 分钟"),
    RadarRefreshOption(180_000, "3 分钟"),
    RadarRefreshOption(300_000, "5 分钟"),
)

CARD_REFRESH_OPTIONS: dict[str, tuple[RadarRefreshOption, ...]] = {
    "discovery_volume_surge": RADAR_DISCOVERY_REFRESH_OPTIONS,
    "discovery_moneyflow_intraday": RADAR_DISCOVERY_REFRESH_OPTIONS,
    "watchlist_intraday": RADAR_WATCHLIST_REFRESH_OPTIONS,
    "sector_theme": RADAR_SECTOR_REFRESH_OPTIONS,
}


@dataclass(frozen=True)
class RadarCardSpec:
    id: str
    title: str
    category: RadarCategory
    top_n: int = 8
    has_task_variants: bool = False
    auto_refresh_ms: int | None = None


@dataclass(frozen=True)
class RadarVariant:
    key: str
    label: str


# 兼容旧名
ScreenTaskVariant = RadarVariant

SCENARIO_VARIANTS: tuple[RadarVariant, ...] = (
    RadarVariant("scenario_bull", "偏多情景"),
    RadarVariant("scenario_volatile", "高波动"),
    RadarVariant("scenario_bear", "偏空情景"),
)

RADAR_CARD_SPECS: tuple[RadarCardSpec, ...] = (
    RadarCardSpec("screen_latest", "选股结果·最新", "screen"),
    RadarCardSpec("screen_task", "选股结果·任务", "screen", has_task_variants=True),
    RadarCardSpec(
        "discovery_volume_surge",
        "发现·放量异动",
        "discovery",
        auto_refresh_ms=RADAR_DISCOVERY_AUTO_REFRESH_MS,
    ),
    RadarCardSpec(
        "discovery_moneyflow_intraday",
        "发现·资金异动",
        "discovery",
        auto_refresh_ms=RADAR_DISCOVERY_AUTO_REFRESH_MS,
    ),
    RadarCardSpec(
        "watchlist_intraday",
        "自选·异动",
        "watchlist",
        auto_refresh_ms=RADAR_WATCHLIST_AUTO_REFRESH_MS,
    ),
    RadarCardSpec(
        "sector_theme",
        "板块·主线",
        "sector",
        has_task_variants=True,
        auto_refresh_ms=RADAR_SECTOR_AUTO_REFRESH_MS,
    ),
    RadarCardSpec("outlook_watch", "未来·关注", "outlook"),
    RadarCardSpec("outlook_hold", "未来·可持", "outlook"),
    RadarCardSpec("outlook_scenario", "未来·情景", "outlook", has_task_variants=True),
)

DEFAULT_SCENARIO_VARIANT = "scenario_bull"

SCREEN_TASK_VARIANTS: tuple[RadarVariant, ...] = (
    RadarVariant("scheduled_intraday", "盘中任务"),
    RadarVariant("scheduled_post_close", "盘后任务"),
    RadarVariant("strategy", "策略选股"),
)

SECTOR_VARIANTS: tuple[RadarVariant, ...] = (
    RadarVariant("leaders", "板块龙头"),
    RadarVariant("breadth", "广度扩散"),
)

DEFAULT_SCREEN_TASK_VARIANT = "scheduled_post_close"
DEFAULT_SECTOR_VARIANT = "leaders"

CARD_VARIANTS: dict[str, tuple[RadarVariant, ...]] = {
    "screen_task": SCREEN_TASK_VARIANTS,
    "sector_theme": SECTOR_VARIANTS,
    "outlook_scenario": SCENARIO_VARIANTS,
}

RADAR_CARD_BY_ID: dict[str, RadarCardSpec] = {spec.id: spec for spec in RADAR_CARD_SPECS}


def list_radar_cards() -> tuple[RadarCardSpec, ...]:
    return RADAR_CARD_SPECS


def variants_for_card(card_id: str) -> tuple[RadarVariant, ...]:
    return CARD_VARIANTS.get(card_id, ())


def default_variant_for_card(card_id: str) -> str:
    defaults = {
        "screen_task": DEFAULT_SCREEN_TASK_VARIANT,
        "sector_theme": DEFAULT_SECTOR_VARIANT,
        "outlook_scenario": DEFAULT_SCENARIO_VARIANT,
    }
    return defaults.get(card_id, "")


def auto_refresh_card_ids() -> tuple[str, ...]:
    return tuple(spec.id for spec in RADAR_CARD_SPECS if spec.auto_refresh_ms is not None)


def manual_only_card_ids() -> tuple[str, ...]:
    return tuple(spec.id for spec in RADAR_CARD_SPECS if spec.auto_refresh_ms is None)


def supports_auto_refresh(card_id: str) -> bool:
    return card_id in CARD_REFRESH_OPTIONS


def refresh_options_for_card(card_id: str) -> tuple[RadarRefreshOption, ...]:
    return CARD_REFRESH_OPTIONS.get(card_id, ())


def default_refresh_ms_for_card(card_id: str) -> int:
    spec = RADAR_CARD_BY_ID.get(card_id)
    if spec is None or spec.auto_refresh_ms is None:
        return RADAR_REFRESH_OFF_MS
    return int(spec.auto_refresh_ms)
