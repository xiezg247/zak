"""雷达页卡片注册表（选股结果 + 发现）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RadarCategory = Literal["screen", "discovery"]


@dataclass(frozen=True)
class RadarCardSpec:
    id: str
    title: str
    category: RadarCategory
    top_n: int = 8
    has_task_variants: bool = False


@dataclass(frozen=True)
class ScreenTaskVariant:
    key: str
    label: str


RADAR_CARD_SPECS: tuple[RadarCardSpec, ...] = (
    RadarCardSpec("screen_latest", "选股结果·最新", "screen"),
    RadarCardSpec("screen_task", "选股结果·任务", "screen", has_task_variants=True),
    RadarCardSpec("discovery_volume_surge", "发现·放量异动", "discovery"),
    RadarCardSpec("discovery_moneyflow_intraday", "发现·资金异动", "discovery"),
)

SCREEN_TASK_VARIANTS: tuple[ScreenTaskVariant, ...] = (
    ScreenTaskVariant("scheduled_intraday", "盘中任务"),
    ScreenTaskVariant("scheduled_post_close", "盘后任务"),
    ScreenTaskVariant("strategy", "策略选股"),
)

DEFAULT_SCREEN_TASK_VARIANT = "scheduled_post_close"

RADAR_CARD_BY_ID: dict[str, RadarCardSpec] = {spec.id: spec for spec in RADAR_CARD_SPECS}


def list_radar_cards() -> tuple[RadarCardSpec, ...]:
    return RADAR_CARD_SPECS
