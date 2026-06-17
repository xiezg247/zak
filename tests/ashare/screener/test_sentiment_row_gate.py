"""情绪门控与 ScreenerResultRow 集成测试。"""

from __future__ import annotations

from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.quotes.market.emotion_cycle import classify_emotion_cycle
from vnpy_ashare.quotes.market.emotion_cycle_inputs import EmotionCycleInputs
from vnpy_ashare.screener.sentiment.emotion_gate import apply_emotion_modulation


def test_emotion_modulation_keeps_screener_result_row_type() -> None:
    snap = classify_emotion_cycle(
        EmotionCycleInputs(
            limit_up_count=55,
            limit_down_count=3,
            up_ratio=0.5,
            total_amount=2e12,
            max_limit_times=4,
            limit_ladder_depth=2,
        ),
    )
    rows = [
        ScreenerResultRow.from_mapping(
            {
                "vt_symbol": "600000.SSE",
                "composite_score": 80.0,
                "hit_reasons": ["动量"],
            },
        ),
    ]
    adjusted, meta = apply_emotion_modulation(rows, snapshot=snap)
    assert isinstance(adjusted[0], ScreenerResultRow)
    assert adjusted[0].scores["composite_score"] < 80.0
    assert meta is not None and "emotion_stage" in meta
