"""short_term_screen 与统一配方联动测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vnpy_ashare.domain.market.emotion import EmotionCycleSnapshot
from vnpy_ashare.screener.run.short_term_screen import run_short_term_screen


def test_short_term_screen_uses_unified_recipe() -> None:
    fake_result = MagicMock()
    fake_result.rows = [
        {
            "vt_symbol": "600000.SSE",
            "symbol": "600000",
            "name": "浦发银行",
            "leader_score": 80,
            "limit_times": 2,
            "dimensions": {"leader_score": 80.0, "radar_resonance": 70.0},
        }
    ]
    fake_result.total_scanned = 500

    cycle = EmotionCycleSnapshot(
        stage="startup",
        stage_label="启动",
        position_pct_min=0.3,
        position_pct_max=0.5,
        position_factor=0.4,
        allowed_modes=("limit_board",),
        allow_new_positions=True,
        warnings=(),
        inputs={},
        updated_at="t",
    )

    with (
        patch(
            "vnpy_ashare.screener.run.short_term_screen.load_emotion_cycle_snapshot",
            return_value=cycle,
        ),
        patch(
            "vnpy_ashare.screener.run.short_term_screen.run_recipe",
            return_value=fake_result,
        ) as mock_run_recipe,
        patch(
            "vnpy_ashare.screener.run.short_term_screen.filter_ultra_short_main_pool",
            side_effect=lambda rows: rows,
        ),
    ):
        result = run_short_term_screen(top_n=5, require_resonance=True)

    mock_run_recipe.assert_called_once()
    assert mock_run_recipe.call_args.args[0] == "ultra_short_unified"
    assert len(result.rows) == 1
    assert "共振" in result.condition
