"""雷达页卡片注册表（选股 / 发现 / 自选 / 板块 / 展望）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RadarCategory = Literal["screen", "discovery", "watchlist", "sector", "outlook"]

RADAR_GRID_COLUMNS = 3


@dataclass(frozen=True)
class RadarCardSpec:
    id: str
    title: str
    category: RadarCategory
    top_n: int = 8
    has_task_variants: bool = False


@dataclass(frozen=True)
class RadarVariant:
    key: str
    label: str


# 兼容旧名
ScreenTaskVariant = RadarVariant

RADAR_CARD_SPECS: tuple[RadarCardSpec, ...] = (
    RadarCardSpec("screen_latest", "选股结果·最新", "screen"),
    RadarCardSpec("screen_task", "选股结果·任务", "screen", has_task_variants=True),
    RadarCardSpec("discovery_volume_surge", "发现·放量异动", "discovery"),
    RadarCardSpec("discovery_moneyflow_intraday", "发现·资金异动", "discovery"),
    RadarCardSpec("watchlist_intraday", "自选·异动", "watchlist"),
    RadarCardSpec("sector_theme", "板块·主线", "sector", has_task_variants=True),
    RadarCardSpec("outlook_watch", "未来·关注", "outlook"),
    RadarCardSpec("outlook_hold", "未来·可持", "outlook"),
)

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
    }
    return defaults.get(card_id, "")
