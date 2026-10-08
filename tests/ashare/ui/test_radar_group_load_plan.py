"""雷达分组加载计划纯函数测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.quotes.radar.loaders import RadarCardData
from vnpy_ashare.ui.quotes.radar.group_load_plan import (
    is_usable_cached_card,
    plan_group_load,
    sort_loaded_cards_for_apply,
)


def _item(card_id: str) -> tuple[str, dict[str, object]]:
    return (card_id, {})


def _card(card_id: str, *, rows: bool = False, empty: str = "") -> RadarCardData:
    from vnpy_ashare.quotes.radar.radar_models import RadarRow

    row_tuple = ()
    if rows:
        row_tuple = (
            RadarRow(
                vt_symbol="600000.SSE",
                name="浦发",
                symbol="600000",
                price=10.0,
                change_pct=1.0,
                metric_label="涨幅",
                metric_value="+1.00%",
                sub_label="",
                sub_value="",
            ),
        )
    return RadarCardData(
        card_id=card_id,
        title=card_id,
        subtitle="",
        rows=row_tuple,
        empty_message=empty,
        updated_at="",
    )


def test_is_usable_cached_card() -> None:
    assert not is_usable_cached_card(None)
    assert not is_usable_cached_card(_card("a"))
    assert is_usable_cached_card(_card("a", empty="暂无数据"))
    assert is_usable_cached_card(_card("a", rows=True))


def test_sort_loaded_cards_for_apply_visible_first() -> None:
    loaded = {
        "hidden": _card("hidden", rows=True),
        "visible": _card("visible", rows=True),
    }
    ordered = sort_loaded_cards_for_apply(loaded, {"visible"})
    assert [card_id for card_id, _ in ordered] == ["visible", "hidden"]


def test_plan_group_load_viewport_split() -> None:
    items = [_item("a"), _item("b"), _item("c")]
    with patch(
        "vnpy_ashare.ui.quotes.radar.group_load_plan.split_radar_items_by_load_priority",
        return_value=[items],
    ):
        plan = plan_group_load(items, visible_ids={"a"})
    assert [cid for cid, _ in plan.run_now] == ["a"]
    assert [cid for cid, _ in plan.deferred_viewport] == ["b", "c"]
    assert plan.deferred_tiers == []


def test_plan_group_load_priority_tiers() -> None:
    tier0 = [_item("market_emotion")]
    tier1 = [_item("leader_pick"), _item("watchlist_short_term")]
    with patch(
        "vnpy_ashare.ui.quotes.radar.group_load_plan.split_radar_items_by_load_priority",
        return_value=[tier0, tier1],
    ):
        plan = plan_group_load(tier0 + tier1, visible_ids={"market_emotion", "leader_pick", "watchlist_short_term"})
    assert [cid for cid, _ in plan.run_now] == ["market_emotion"]
    assert plan.deferred_viewport == []
    assert plan.deferred_tiers == [tier1]


def test_plan_group_load_skip_viewport_keeps_items() -> None:
    items = [_item("a"), _item("b")]
    plan = plan_group_load(items, visible_ids={"a"}, skip_viewport_split=True)
    assert plan.run_now == list(items)
    assert plan.deferred_viewport == []
    assert plan.deferred_tiers == []
