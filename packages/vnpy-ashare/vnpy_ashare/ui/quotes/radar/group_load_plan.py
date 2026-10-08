"""雷达分组加载计划（视口优先 + 优先级分批；纯函数）。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from vnpy_ashare.quotes.radar.loaders import RadarCardData
from vnpy_ashare.quotes.radar.radar_catalog import split_radar_items_by_load_priority

RadarLoadItem = tuple[str, dict[str, object]]

RADAR_GROUP_LOAD_MIN_CARDS = 2


@dataclass(frozen=True)
class GroupLoadPlan:
    """一次 ``_start_group_load`` 的执行计划。"""

    run_now: list[RadarLoadItem]
    deferred_viewport: list[RadarLoadItem]
    deferred_tiers: list[list[RadarLoadItem]]


def is_usable_cached_card(data: RadarCardData | None) -> bool:
    """缓存卡片是否可先展示（有行或有空态文案）。"""
    if data is None:
        return False
    if not data.rows and not data.empty_message:
        return False
    return True


def sort_loaded_cards_for_apply(
    loaded: Mapping[str, RadarCardData],
    visible_ids: set[str] | frozenset[str],
) -> list[tuple[str, RadarCardData]]:
    """可见卡优先入队 apply，降低首屏等待。"""
    return sorted(
        loaded.items(),
        key=lambda item: 0 if item[0] in visible_ids else 1,
    )


def plan_group_load(
    items: Sequence[RadarLoadItem],
    *,
    visible_ids: set[str] | frozenset[str],
    min_cards: int = RADAR_GROUP_LOAD_MIN_CARDS,
    skip_viewport_split: bool = False,
) -> GroupLoadPlan:
    """按优先级分批，再按视口拆出本轮立即加载与延后项。"""
    working = list(items)
    deferred_tiers: list[list[RadarLoadItem]] = []
    if not skip_viewport_split:
        priority_batches = split_radar_items_by_load_priority(working)
        if len(priority_batches) > 1:
            deferred_tiers = priority_batches[1:]
            working = priority_batches[0]

    if not skip_viewport_split and len(working) >= min_cards:
        priority = [(card_id, kwargs) for card_id, kwargs in working if card_id in visible_ids]
        deferred = [(card_id, kwargs) for card_id, kwargs in working if card_id not in visible_ids]
        if priority and deferred:
            return GroupLoadPlan(
                run_now=priority,
                deferred_viewport=deferred,
                deferred_tiers=deferred_tiers,
            )

    return GroupLoadPlan(
        run_now=working,
        deferred_viewport=[],
        deferred_tiers=deferred_tiers,
    )
