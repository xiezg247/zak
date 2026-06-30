"""雷达页卡片注册表（选股 / 发现 / 自选 / 板块 / 展望）。"""

from __future__ import annotations

from typing import Literal

from vnpy_ashare.domain.radar.catalog import (
    RadarCardMode,
    RadarCardSpec,
    RadarCategory,
    RadarLayoutSection,
    RadarRefreshOption,
    RadarVariant,
)
from vnpy_ashare.quotes.radar.radar_full_refresh_prefs import (
    full_refresh_every_n_ticks as _load_full_refresh_every_n_ticks,
)
from vnpy_ashare.quotes.radar.radar_resonance_prefs import (
    radar_card_resonance_weight as _load_radar_card_resonance_weight,
)

__all__ = [
    "CARD_REFRESH_OPTIONS",
    "RADAR_CARD_SPECS",
    "RADAR_DISCOVERY_AUTO_REFRESH_MS",
    "RADAR_DISCOVERY_REFRESH_OPTIONS",
    "RADAR_GRID_COLUMNS",
    "RADAR_LAYOUT_SECTIONS",
    "RADAR_REFRESH_OFF_MS",
    "RADAR_SECTOR_AUTO_REFRESH_MS",
    "RADAR_SECTOR_REFRESH_OPTIONS",
    "RADAR_WATCHLIST_AUTO_REFRESH_MS",
    "RADAR_WATCHLIST_REFRESH_OPTIONS",
    "SCENARIO_VARIANTS",
    "RadarCardMode",
    "RadarCardSpec",
    "RadarCategory",
    "RadarGroupKey",
    "RadarLayoutSection",
    "RadarRefreshOption",
    "RadarVariant",
    "default_group_for_mode",
    "full_refresh_every_n_ticks",
    "list_radar_cards",
    "list_radar_cards_for_group",
    "list_radar_cards_for_mode",
    "list_radar_groups_for_mode",
    "radar_card_group",
    "radar_card_resonance_weight",
    "refresh_options_for_card",
]

RADAR_GRID_COLUMNS = 3

# 盘中敏感卡默认自动刷新间隔（展望/选股仅手动或读缓存）
RADAR_REFRESH_OFF_MS = 0
RADAR_DISCOVERY_AUTO_REFRESH_MS = 60_000
RADAR_WATCHLIST_AUTO_REFRESH_MS = 60_000
RADAR_SECTOR_AUTO_REFRESH_MS = 180_000


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
    "discovery_limit_break": RADAR_DISCOVERY_REFRESH_OPTIONS,
    "sector_flow_hot": RADAR_SECTOR_REFRESH_OPTIONS,
    "watchlist_intraday": RADAR_WATCHLIST_REFRESH_OPTIONS,
    "watchlist_short_term": RADAR_WATCHLIST_REFRESH_OPTIONS,
    "position_risk": RADAR_WATCHLIST_REFRESH_OPTIONS,
    "sector_theme": RADAR_SECTOR_REFRESH_OPTIONS,
}


RADAR_LAYOUT_SECTIONS: tuple[RadarLayoutSection, ...] = (
    RadarLayoutSection(mode="statistical", title="盘面统计", hint="盘中异动与板块主线，描述当前盘面"),
    RadarLayoutSection(mode="predictive", title="前瞻展望", hint="策略信号与统计情景，非确定性预测"),
)

RadarGroupKey = Literal["leader", "discovery", "portfolio", "signals", "forecast"]

_STATISTICAL_GROUPS: tuple[tuple[RadarGroupKey, str], ...] = (
    ("leader", "龙头选股"),
    ("discovery", "盘中发现"),
    ("portfolio", "板块自选"),
)

_PREDICTIVE_GROUPS: tuple[tuple[RadarGroupKey, str], ...] = (
    ("signals", "策略信号"),
    ("forecast", "情景预测"),
)

_RADAR_GROUPS_BY_MODE: dict[RadarCardMode, tuple[tuple[RadarGroupKey, str], ...]] = {
    "statistical": _STATISTICAL_GROUPS,
    "predictive": _PREDICTIVE_GROUPS,
}

_DEFAULT_GROUP_BY_MODE: dict[RadarCardMode, RadarGroupKey] = {
    "statistical": "leader",
    "predictive": "signals",
}

RADAR_CARD_GROUP: dict[str, RadarGroupKey] = {
    "leader_pick": "leader",
    "watchlist_short_term": "leader",
    "discovery_limit_ladder": "discovery",
    "discovery_limit_break": "discovery",
    "discovery_volume_surge": "discovery",
    "discovery_moneyflow_intraday": "discovery",
    "sector_flow_hot": "discovery",
    "sector_theme": "portfolio",
    "watchlist_intraday": "portfolio",
    "position_risk": "portfolio",
    "outlook_watch": "signals",
    "outlook_hold": "signals",
    "outlook_scenario": "forecast",
    "outlook_predict": "forecast",
}


def list_radar_groups_for_mode(mode: RadarCardMode) -> tuple[tuple[RadarGroupKey, str], ...]:
    return _RADAR_GROUPS_BY_MODE.get(mode, ())


def default_group_for_mode(mode: RadarCardMode) -> RadarGroupKey:
    return _DEFAULT_GROUP_BY_MODE.get(mode, "leader")


def radar_card_group(card_id: str) -> RadarGroupKey | None:
    return RADAR_CARD_GROUP.get(card_id)


def list_radar_cards_for_group(mode: RadarCardMode, group_key: RadarGroupKey) -> tuple[RadarCardSpec, ...]:
    return tuple(spec for spec in RADAR_CARD_SPECS if spec.mode == mode and RADAR_CARD_GROUP.get(spec.id) == group_key)


# 龙头分组首屏：leader_pick 最先加载
RADAR_CARD_LOAD_PRIORITY: dict[str, int] = {
    "leader_pick": 0,
    "watchlist_short_term": 1,
}


def split_radar_items_by_load_priority(
    items: list[tuple[str, dict[str, object]]],
) -> list[list[tuple[str, dict[str, object]]]]:
    """按卡片优先级拆成多批；未列出的卡片优先级 0，同批一起加载。"""
    tiers: dict[int, list[tuple[str, dict[str, object]]]] = {}
    for card_id, kwargs in items:
        tier = RADAR_CARD_LOAD_PRIORITY.get(card_id, 0)
        tiers.setdefault(tier, []).append((card_id, kwargs))
    return [tiers[k] for k in sorted(tiers.keys())]


SCENARIO_VARIANTS: tuple[RadarVariant, ...] = (
    RadarVariant(key="scenario_bull", label="偏多情景"),
    RadarVariant(key="scenario_volatile", label="高波动"),
    RadarVariant(key="scenario_bear", label="偏空情景"),
)

RADAR_CARD_SPECS: tuple[RadarCardSpec, ...] = (
    RadarCardSpec(id="leader_pick", title="选股·龙头", category="screen", top_n=12),
    RadarCardSpec(id="watchlist_short_term", title="自选·短线关注", category="watchlist", top_n=10, auto_refresh_ms=RADAR_WATCHLIST_AUTO_REFRESH_MS),
    RadarCardSpec(
        id="discovery_limit_ladder", title="发现·连板梯队", category="discovery", has_task_variants=True, auto_refresh_ms=RADAR_DISCOVERY_AUTO_REFRESH_MS
    ),
    RadarCardSpec(id="discovery_limit_break", title="发现·炸板断板", category="discovery", top_n=10, auto_refresh_ms=RADAR_DISCOVERY_AUTO_REFRESH_MS),
    RadarCardSpec(id="discovery_volume_surge", title="发现·放量异动", category="discovery", auto_refresh_ms=RADAR_DISCOVERY_AUTO_REFRESH_MS),
    RadarCardSpec(id="discovery_moneyflow_intraday", title="发现·资金异动", category="discovery", auto_refresh_ms=RADAR_DISCOVERY_AUTO_REFRESH_MS),
    RadarCardSpec(
        id="sector_flow_hot", title="板块·资金热度", category="sector", has_task_variants=True, top_n=8, auto_refresh_ms=RADAR_SECTOR_AUTO_REFRESH_MS
    ),
    RadarCardSpec(id="sector_theme", title="板块·主线", category="sector", has_task_variants=True, auto_refresh_ms=RADAR_SECTOR_AUTO_REFRESH_MS),
    RadarCardSpec(id="watchlist_intraday", title="自选·异动", category="watchlist", auto_refresh_ms=RADAR_WATCHLIST_AUTO_REFRESH_MS),
    RadarCardSpec(id="position_risk", title="持仓·风控", category="watchlist", auto_refresh_ms=RADAR_WATCHLIST_AUTO_REFRESH_MS),
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

SECTOR_VARIANTS: tuple[RadarVariant, ...] = (
    RadarVariant(key="leaders_tiered", label="行业龙一"),
    RadarVariant(key="concept_leaders", label="概念龙一"),
    RadarVariant(key="breadth", label="广度扩散"),
)

LEADER_PICK_VARIANTS: tuple[RadarVariant, ...] = (
    RadarVariant(key="mainline", label="主线龙头"),
    RadarVariant(key="all_market", label="全市场"),
)

LIMIT_LADDER_VARIANTS: tuple[RadarVariant, ...] = (
    RadarVariant(key="by_height", label="按高度"),
    RadarVariant(key="by_sector", label="按板块"),
    RadarVariant(key="first_board", label="首板人气"),
)

SECTOR_FLOW_HOT_VARIANTS: tuple[RadarVariant, ...] = (
    RadarVariant(key="industry", label="行业"),
    RadarVariant(key="concept", label="概念"),
)

DEFAULT_SCREEN_TASK_VARIANT = "scheduled_post_close"
DEFAULT_SECTOR_VARIANT = "leaders_tiered"
DEFAULT_LEADER_PICK_VARIANT = "mainline"
DEFAULT_LIMIT_LADDER_VARIANT = "by_height"
DEFAULT_SECTOR_FLOW_HOT_VARIANT = "industry"

CARD_VARIANTS: dict[str, tuple[RadarVariant, ...]] = {
    "sector_theme": SECTOR_VARIANTS,
    "sector_flow_hot": SECTOR_FLOW_HOT_VARIANTS,
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
        "sector_theme": DEFAULT_SECTOR_VARIANT,
        "sector_flow_hot": DEFAULT_SECTOR_FLOW_HOT_VARIANT,
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
