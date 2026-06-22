"""雷达全页快照领域模型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.domain.radar.card import RadarResonanceEntry, RadarRow
from vnpy_common.domain.base import FrozenModel


class RadarLimitLadderSummary(FrozenModel):
    total: int = Field(default=0, description="连板梯队行数")
    max_limit_times: float = Field(default=0.0, description="最高连板数")
    top_vt_symbols: tuple[str, ...] = Field(default=(), description="梯队前列 vt_symbol")


class RadarBoardSnapshot(FrozenModel):
    board_updated_at: str = Field(default="", description="快照构建时间")
    emotion_stage: str = Field(default="", description="情绪阶段 key")
    emotion_stage_label: str = Field(default="", description="情绪阶段中文")
    allow_new_positions: bool = Field(default=True, description="是否允许短线新开")
    resonance_entries: tuple[RadarResonanceEntry, ...] = Field(default=(), description="共振列表")
    leader_pick_rows: tuple[RadarRow, ...] = Field(default=(), description="选股·龙头卡行")
    limit_ladder_summary: RadarLimitLadderSummary = Field(
        default_factory=RadarLimitLadderSummary,
        description="连板梯队摘要",
    )
    card_updated_at: tuple[tuple[str, str], ...] = Field(default=(), description="各卡 updated_at")
    resonance_count: int = Field(default=0, description="共振标的数")
    dragon_1_count: int = Field(default=0, description="龙一数量（leader_pick）")
