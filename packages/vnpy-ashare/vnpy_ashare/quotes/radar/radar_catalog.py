"""雷达页卡片注册表（选股 / 发现 / 自选 / 板块 / 展望）。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel
from vnpy_ashare.quotes.radar.radar_full_refresh_prefs import (
    full_refresh_every_n_ticks as _load_full_refresh_every_n_ticks,
)
from vnpy_ashare.quotes.radar.radar_resonance_prefs import (
    radar_card_resonance_weight as _load_radar_card_resonance_weight,
)

RadarCategory = Literal["screen", "discovery", "watchlist", "sector", "outlook"]
RadarCardMode = Literal["statistical", "predictive"]

RADAR_GRID_COLUMNS = 3

# 盘中敏感卡默认自动刷新间隔（展望/选股仅手动或读缓存）
RADAR_REFRESH_OFF_MS = 0
RADAR_DISCOVERY_AUTO_REFRESH_MS = 60_000
RADAR_WATCHLIST_AUTO_REFRESH_MS = 60_000
RADAR_SECTOR_AUTO_REFRESH_MS = 180_000


class RadarRefreshOption(FrozenModel):
    ms: int = Field(description="刷新间隔（毫秒）")
    label: str = Field(description="展示标签")


RADAR_DISCOVERY_REFRESH_OPTIONS: tuple[RadarRefreshOption, ...] = (
    RadarRefreshOption(ms=RADAR_REFRESH_OFF_MS, label="不刷新"),
    RadarRefreshOption(ms=30000, label="30 秒"),
    RadarRefreshOption(ms=60000, label="1 分钟"),
    RadarRefreshOption(ms=120000, label="2 分钟"),
)

RADAR_WATCHLIST_REFRESH_OPTIONS: tuple[RadarRefreshOption, ...] = RADAR_DISCOVERY_REFRESH_OPTIONS

RADAR_SECTOR_REFRESH_OPTIONS: tuple[RadarRefreshOption, ...] = (
    RadarRefreshOption(ms=RADAR_REFRESH_OFF_MS, label="不刷新"),
    RadarRefreshOption(ms=60000, label="1 分钟"),
    RadarRefreshOption(ms=180000, label="3 分钟"),
    RadarRefreshOption(ms=300000, label="5 分钟"),
)

CARD_REFRESH_OPTIONS: dict[str, tuple[RadarRefreshOption, ...]] = {
    "discovery_volume_surge": RADAR_DISCOVERY_REFRESH_OPTIONS,
    "discovery_moneyflow_intraday": RADAR_DISCOVERY_REFRESH_OPTIONS,
    "discovery_limit_ladder": RADAR_DISCOVERY_REFRESH_OPTIONS,
    "discovery_first_board": RADAR_DISCOVERY_REFRESH_OPTIONS,
    "watchlist_intraday": RADAR_WATCHLIST_REFRESH_OPTIONS,
    "sector_theme": RADAR_SECTOR_REFRESH_OPTIONS,
}


class RadarLayoutSection(FrozenModel):
    mode: RadarCardMode = Field(description="模式")
    title: str = Field(description="标题")
    hint: str = Field(description="提示文案")


RADAR_LAYOUT_SECTIONS: tuple[RadarLayoutSection, ...] = (
    RadarLayoutSection(mode="statistical", title="盘面统计", hint="选股结果、盘中异动与板块主线，描述当前盘面"),
    RadarLayoutSection(mode="predictive", title="前瞻展望", hint="策略信号与统计情景，非确定性预测"),
)


class RadarCardSpec(FrozenModel):
    id: str = Field(description="主键 ID")
    title: str = Field(description="标题")
    category: RadarCategory = Field(description="分类")
    mode: RadarCardMode = Field(default="statistical", description="mode")
    top_n: int = Field(default=8, description="top n")
    has_task_variants: bool = Field(default=False, description="has task variants")
    auto_refresh_ms: int | None = Field(default=None, description="auto refresh ms")


class RadarVariant(FrozenModel):
    key: str = Field(description="键名")
    label: str = Field(description="展示标签")


SCENARIO_VARIANTS: tuple[RadarVariant, ...] = (
    RadarVariant(key="scenario_bull", label="偏多情景"),
    RadarVariant(key="scenario_volatile", label="高波动"),
    RadarVariant(key="scenario_bear", label="偏空情景"),
)

RADAR_CARD_SPECS: tuple[RadarCardSpec, ...] = (
    RadarCardSpec(id="screen_latest", title="选股结果·最新", category="screen"),
    RadarCardSpec(id="screen_task", title="选股结果·任务", category="screen", has_task_variants=True),
    RadarCardSpec(id="discovery_volume_surge", title="发现·放量异动", category="discovery", auto_refresh_ms=RADAR_DISCOVERY_AUTO_REFRESH_MS),
    RadarCardSpec(id="discovery_moneyflow_intraday", title="发现·资金异动", category="discovery", auto_refresh_ms=RADAR_DISCOVERY_AUTO_REFRESH_MS),
    RadarCardSpec(
        id="discovery_limit_ladder", title="发现·连板梯队", category="discovery", has_task_variants=True, auto_refresh_ms=RADAR_DISCOVERY_AUTO_REFRESH_MS
    ),
    RadarCardSpec(id="discovery_first_board", title="发现·首板人气", category="discovery", auto_refresh_ms=RADAR_DISCOVERY_AUTO_REFRESH_MS),
    RadarCardSpec(id="watchlist_intraday", title="自选·异动", category="watchlist", auto_refresh_ms=RADAR_WATCHLIST_AUTO_REFRESH_MS),
    RadarCardSpec(id="sector_theme", title="板块·主线", category="sector", has_task_variants=True, auto_refresh_ms=RADAR_SECTOR_AUTO_REFRESH_MS),
    RadarCardSpec(id="leader_pick", title="选股·龙头", category="screen", top_n=12),
    RadarCardSpec(id="outlook_watch", title="未来·关注", category="outlook", mode="predictive"),
    RadarCardSpec(id="outlook_hold", title="未来·可持", category="outlook", mode="predictive"),
    RadarCardSpec(id="outlook_scenario", title="未来·情景", category="outlook", mode="predictive", has_task_variants=True),
    RadarCardSpec(id="outlook_predict", title="未来·预测", category="outlook", mode="predictive", has_task_variants=True),
)

PREDICT_MODEL_VARIANTS: tuple[RadarVariant, ...] = (
    RadarVariant(key="auto", label="自动"),
    RadarVariant(key="baseline", label="统计基线"),
)

DEFAULT_PREDICT_MODEL_VARIANT = "auto"

DEFAULT_SCENARIO_VARIANT = "scenario_bull"

SCREEN_TASK_VARIANTS: tuple[RadarVariant, ...] = (
    RadarVariant(key="scheduled_intraday", label="盘中任务"),
    RadarVariant(key="scheduled_post_close", label="盘后任务"),
    RadarVariant(key="strategy", label="条件选股"),
)

SECTOR_VARIANTS: tuple[RadarVariant, ...] = (
    RadarVariant(key="leaders_tiered", label="龙一分层"),
    RadarVariant(key="breadth", label="广度扩散"),
)

LEADER_PICK_VARIANTS: tuple[RadarVariant, ...] = (
    RadarVariant(key="mainline", label="主线龙头"),
    RadarVariant(key="all_market", label="全市场"),
)

LIMIT_LADDER_VARIANTS: tuple[RadarVariant, ...] = (
    RadarVariant(key="by_height", label="按高度"),
    RadarVariant(key="by_sector", label="按板块"),
)

DEFAULT_SCREEN_TASK_VARIANT = "scheduled_post_close"
DEFAULT_SECTOR_VARIANT = "leaders_tiered"
DEFAULT_LEADER_PICK_VARIANT = "mainline"
DEFAULT_LIMIT_LADDER_VARIANT = "by_height"

CARD_VARIANTS: dict[str, tuple[RadarVariant, ...]] = {
    "screen_task": SCREEN_TASK_VARIANTS,
    "sector_theme": SECTOR_VARIANTS,
    "leader_pick": LEADER_PICK_VARIANTS,
    "discovery_limit_ladder": LIMIT_LADDER_VARIANTS,
    "outlook_scenario": SCENARIO_VARIANTS,
    "outlook_predict": PREDICT_MODEL_VARIANTS,
}

RADAR_CARD_BY_ID: dict[str, RadarCardSpec] = {spec.id: spec for spec in RADAR_CARD_SPECS}


def list_radar_cards() -> tuple[RadarCardSpec, ...]:
    return RADAR_CARD_SPECS


def list_radar_cards_for_mode(mode: RadarCardMode) -> tuple[RadarCardSpec, ...]:
    return tuple(spec for spec in RADAR_CARD_SPECS if spec.mode == mode)


def radar_card_mode(card_id: str) -> RadarCardMode:
    spec = RADAR_CARD_BY_ID.get(card_id)
    if spec is None:
        msg = f"未知雷达卡片：{card_id}"
        raise ValueError(msg)
    return spec.mode


def variants_for_card(card_id: str) -> tuple[RadarVariant, ...]:
    return CARD_VARIANTS.get(card_id, ())


def default_variant_for_card(card_id: str) -> str:
    defaults = {
        "screen_task": DEFAULT_SCREEN_TASK_VARIANT,
        "sector_theme": DEFAULT_SECTOR_VARIANT,
        "leader_pick": DEFAULT_LEADER_PICK_VARIANT,
        "discovery_limit_ladder": DEFAULT_LIMIT_LADDER_VARIANT,
        "outlook_scenario": DEFAULT_SCENARIO_VARIANT,
        "outlook_predict": DEFAULT_PREDICT_MODEL_VARIANT,
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


def full_refresh_every_n_ticks(card_id: str) -> int:
    """自动刷新时每隔多少次触发一次全量指标重算。"""
    return _load_full_refresh_every_n_ticks(card_id)


def full_refresh_options_for_card(card_id: str) -> tuple[RadarRefreshOption, ...]:
    if card_id not in CARD_REFRESH_OPTIONS:
        return ()
    return (
        RadarRefreshOption(ms=1, label="每次全量"),
        RadarRefreshOption(ms=2, label="每2次"),
        RadarRefreshOption(ms=3, label="每3次"),
        RadarRefreshOption(ms=5, label="每5次"),
        RadarRefreshOption(ms=10, label="每10次"),
    )


def radar_card_resonance_weight(card_id: str) -> float:
    return _load_radar_card_resonance_weight(card_id)
