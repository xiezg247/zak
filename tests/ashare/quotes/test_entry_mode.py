"""entry_mode 评估测试。"""

from __future__ import annotations

from vnpy_ashare.quotes.analysis.entry_mode import evaluate_entry_mode
from vnpy_ashare.quotes.market.emotion_cycle import EmotionCycleSnapshot


def _cycle(
    stage: str,
    *,
    stage_label: str = "",
    modes: tuple[str, ...] = ("limit_board", "halfway", "pullback"),
) -> EmotionCycleSnapshot:
    allow = stage not in {"recession", "ice"}
    return EmotionCycleSnapshot(
        stage=stage,  # type: ignore[arg-type]
        stage_label=stage_label or stage,
        position_pct_min=0.3 if allow else 0.0,
        position_pct_max=0.5 if allow else 0.0,
        position_factor=0.4 if allow else 0.0,
        allowed_modes=modes,
        allow_new_positions=allow,
        warnings=(),
        inputs={"limit_up_count": 60, "limit_down_count": 5},
        updated_at="2026-06-17",
    )


def test_10cm_limit_board_recommended_at_limit() -> None:
    row = {"vt_symbol": "600519.SSE", "symbol": "600519", "name": "茅台", "change_pct": 10.0}
    result = evaluate_entry_mode(row, cycle=_cycle("climax", stage_label="发酵/高潮"))
    assert result is not None
    assert result.recommended_mode == "limit_board"
    assert result.board_tag == "10cm"


def test_20cm_discourages_limit_board() -> None:
    row = {"vt_symbol": "300001.SZSE", "symbol": "300001", "name": "特锐德", "change_pct": 12.0}
    result = evaluate_entry_mode(row, cycle=_cycle("startup", modes=("halfway", "pullback")))
    assert result is not None
    assert result.recommended_mode in {"halfway", "pullback"}
    assert result.board_tag == "20cm"


def test_recession_no_recommendation() -> None:
    row = {"vt_symbol": "600519.SSE", "symbol": "600519", "change_pct": 10.0}
    result = evaluate_entry_mode(row, cycle=_cycle("recession", stage_label="退潮", modes=()))
    assert result is not None
    assert result.recommended_mode is None
    assert result.allow_new_positions is False
