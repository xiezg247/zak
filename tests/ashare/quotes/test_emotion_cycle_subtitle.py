"""情绪周期 subtitle 后缀测试。"""

from __future__ import annotations

from vnpy_ashare.quotes.market.emotion_cycle import EmotionCycleSnapshot
from vnpy_ashare.quotes.market.emotion_cycle_subtitle import append_emotion_cycle_to_subtitle


def test_append_emotion_suffix() -> None:
    cycle = EmotionCycleSnapshot(
        stage="startup",
        stage_label="启动",
        position_pct_min=0.3,
        position_pct_max=0.5,
        position_factor=0.4,
        allowed_modes=("limit_board", "halfway"),
        allow_new_positions=True,
        warnings=(),
        inputs={},
        updated_at="2026-06-17",
    )
    text = append_emotion_cycle_to_subtitle("Top 10", snapshot=cycle)
    assert "环境：启动" in text
    assert "建议 30–50%" in text
