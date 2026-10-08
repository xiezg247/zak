"""雷达分组加载流水线状态（deferred 视口/分批 + sibling 预取）。"""

from __future__ import annotations

from vnpy_ashare.ui.quotes.radar.group_load_plan import GroupLoadPlan, RadarLoadItem


class RadarLoadPipeline:
    """显式持有「当前组加载后续」与「旁路预取」状态，避免散落在 controller 字段上。"""

    def __init__(self) -> None:
        self.deferred_viewport: list[RadarLoadItem] = []
        self.deferred_tiers: list[list[RadarLoadItem]] = []
        self.prefetch_mode: str | None = None
        self.prefetch_siblings: list[str] = []

    def reset(self) -> None:
        self.clear_deferred()
        self.clear_prefetch()

    def clear_deferred(self) -> None:
        self.deferred_viewport.clear()
        self.deferred_tiers.clear()

    def clear_prefetch(self) -> None:
        self.prefetch_mode = None
        self.prefetch_siblings.clear()

    def apply_plan(self, plan: GroupLoadPlan, *, fresh: bool) -> None:
        """写入新计划。``fresh=True`` 时清空旧 deferred/prefetch（新开一轮分组加载）。"""
        if fresh:
            self.clear_deferred()
            self.clear_prefetch()
        self.deferred_viewport = list(plan.deferred_viewport)
        if plan.deferred_tiers:
            self.deferred_tiers = [list(batch) for batch in plan.deferred_tiers]

    def pop_continuation(self) -> list[RadarLoadItem] | None:
        """取出下一批延后加载；无则返回 None（可进入 prefetch）。"""
        if self.deferred_viewport:
            items = self.deferred_viewport
            self.deferred_viewport = []
            return items
        if self.deferred_tiers:
            return self.deferred_tiers.pop(0)
        return None

    def arm_prefetch(self, mode: str, siblings: list[str]) -> None:
        self.prefetch_mode = mode
        self.prefetch_siblings = list(siblings)

    def prefetch_still_valid(self, current_mode: str) -> bool:
        if self.prefetch_mode is None or current_mode != self.prefetch_mode:
            self.clear_prefetch()
            return False
        return True

    def pop_prefetch_sibling(self) -> str | None:
        if not self.prefetch_siblings:
            return None
        return self.prefetch_siblings.pop(0)

    @property
    def has_prefetch(self) -> bool:
        return bool(self.prefetch_siblings)
