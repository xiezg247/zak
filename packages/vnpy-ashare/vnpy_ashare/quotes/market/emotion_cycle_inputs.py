"""情绪周期输入聚合（广度 + 连板梯队 + 可选辅助因子）。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel, MutableModel

from typing import Any

from vnpy_ashare.quotes.core.limit_times_cache import get_cached_limit_times_map
from vnpy_ashare.quotes.market.market_breadth import MarketBreadthSnapshot
from vnpy_ashare.screener.sentiment.fear_greed_provider import try_fetch_fear_greed_index


class EmotionCycleInputs(FrozenModel):
    limit_up_count: int = Field(description="涨停家数")
    limit_down_count: int = Field(description="跌停家数")
    up_ratio: float = Field(description="上涨占比（0–1）")
    total_amount: float = Field(description="成交额合计")
    max_limit_times: int = Field(description="最高连板数")
    limit_ladder_depth: int = Field(description="连板梯队层数")
    index_above_ma5: bool | None = Field(default=None, description="大盘是否在5日均线上方")
    fear_greed_index: float | None = Field(default=None, description="恐贪指数")
    updated_at: str | None = Field(default=None, description="数据更新时间")


def compute_limit_ladder_stats(limit_times_map: dict[str, float]) -> tuple[int, int]:
    """返回 (最高连板, 梯队层数)。"""
    if not limit_times_map:
        return 0, 0
    boards = [max(0, int(value)) for value in limit_times_map.values()]
    max_boards = max(boards)
    levels = {board for board in boards if board >= 2}
    return max_boards, len(levels)


def build_emotion_cycle_inputs(
    breadth: MarketBreadthSnapshot,
    *,
    limit_times_map: dict[str, float] | None = None,
    index_above_ma5: bool | None = None,
    fear_greed_index: float | None = None,
    include_auxiliary: bool = True,
) -> EmotionCycleInputs:
    up_total = breadth.up + breadth.down
    up_ratio = (breadth.up / up_total) if up_total > 0 else 0.0
    if limit_times_map is None:
        limit_map = get_cached_limit_times_map()
    else:
        limit_map = limit_times_map
    max_limit_times, ladder_depth = compute_limit_ladder_stats(limit_map)

    fg = fear_greed_index
    if include_auxiliary and fg is None:
        snapshot = try_fetch_fear_greed_index()
        if snapshot is not None:
            fg = float(snapshot.index)

    return EmotionCycleInputs(
        limit_up_count=breadth.limit_up,
        limit_down_count=breadth.limit_down,
        up_ratio=up_ratio,
        total_amount=breadth.total_amount,
        max_limit_times=max_limit_times,
        limit_ladder_depth=ladder_depth,
        index_above_ma5=index_above_ma5,
        fear_greed_index=fg,
        updated_at=breadth.updated_at,
    )
