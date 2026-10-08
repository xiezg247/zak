"""雷达加载流水线状态测试。"""

from __future__ import annotations

from vnpy_ashare.ui.quotes.radar.group_load_plan import GroupLoadPlan
from vnpy_ashare.ui.quotes.radar.load_pipeline import RadarLoadPipeline


def _item(card_id: str) -> tuple[str, dict[str, object]]:
    return (card_id, {})


def test_apply_plan_fresh_clears_prefetch() -> None:
    pipeline = RadarLoadPipeline()
    pipeline.arm_prefetch("statistical", ["discovery"])
    plan = GroupLoadPlan(run_now=[_item("a")], deferred_viewport=[_item("b")], deferred_tiers=[[_item("c")]])
    pipeline.apply_plan(plan, fresh=True)
    assert pipeline.deferred_viewport == [_item("b")]
    assert pipeline.deferred_tiers == [[_item("c")]]
    assert pipeline.prefetch_mode is None
    assert pipeline.prefetch_siblings == []


def test_apply_plan_continuation_keeps_tiers() -> None:
    pipeline = RadarLoadPipeline()
    pipeline.deferred_tiers = [[_item("tier")]]
    plan = GroupLoadPlan(run_now=[_item("a")], deferred_viewport=[], deferred_tiers=[])
    pipeline.apply_plan(plan, fresh=False)
    assert pipeline.deferred_tiers == [[_item("tier")]]


def test_pop_continuation_order() -> None:
    pipeline = RadarLoadPipeline()
    pipeline.deferred_viewport = [_item("v")]
    pipeline.deferred_tiers = [[_item("t1")], [_item("t2")]]
    assert pipeline.pop_continuation() == [_item("v")]
    assert pipeline.pop_continuation() == [_item("t1")]
    assert pipeline.pop_continuation() == [_item("t2")]
    assert pipeline.pop_continuation() is None


def test_prefetch_mode_invalidation() -> None:
    pipeline = RadarLoadPipeline()
    pipeline.arm_prefetch("statistical", ["discovery", "portfolio"])
    assert pipeline.prefetch_still_valid("statistical")
    assert not pipeline.prefetch_still_valid("predictive")
    assert pipeline.prefetch_mode is None
