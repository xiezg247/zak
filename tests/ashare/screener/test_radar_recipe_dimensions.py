"""雷达配方维度测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.screener.dimensions.leader_score_dim import run_leader_score
from vnpy_ashare.screener.dimensions.radar_resonance import run_radar_resonance
from vnpy_ashare.screener.recipe.recipe import resolve_recipe


def test_ultra_short_unified_recipe_registered() -> None:
    recipe = resolve_recipe("ultra_short_unified")
    assert recipe is not None
    assert recipe.name == "极致短线·雷达统一"
    dim_ids = {spec.dimension_id for spec in recipe.dimensions}
    assert "leader_score" in dim_ids
    assert "radar_resonance" in dim_ids
    assert "limit_board" in dim_ids


def test_run_leader_score_dimension() -> None:
    fake_rows = [
        {
            "vt_symbol": "600000.SSE",
            "symbol": "600000",
            "name": "浦发银行",
            "leader_score": 85.0,
            "leader_tier": "dragon_1",
            "industry": "银行",
        }
    ]

    with patch(
        "vnpy_ashare.screener.dimensions.leader_score_dim.build_leader_score_dimension_rows",
        return_value=(fake_rows, 100),
    ):
        hits, total = run_leader_score(10, weight=0.3)

    assert total == 100
    assert len(hits) == 1
    assert hits[0].dimension_id == "leader_score"
    assert hits[0].score > 0


def test_run_radar_resonance_dimension() -> None:
    fake_rows = [
        {
            "vt_symbol": "600519.SSE",
            "symbol": "600519",
            "name": "贵州茅台",
            "resonance_score": 5.5,
            "resonance_card_count": 3,
        }
    ]

    with patch(
        "vnpy_ashare.screener.dimensions.radar_resonance.build_radar_resonance_dimension_rows",
        return_value=(fake_rows, 200),
    ):
        hits, total = run_radar_resonance(10, weight=0.2)

    assert total == 200
    assert len(hits) == 1
    assert hits[0].dimension_id == "radar_resonance"
