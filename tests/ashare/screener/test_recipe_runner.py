"""多维度选股配方执行测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.screener.dimensions.base import DimensionHit
from vnpy_ashare.screener.hard_filters import apply_recipe_filters
from vnpy_ashare.screener.recipe.recipe import resolve_recipe
from vnpy_ashare.screener.recipe.recipe_runner import build_reason_summary, run_recipe


def _momentum_hit(row: dict, *, weight: float = 0.35) -> DimensionHit:
    return DimensionHit(
        vt_symbol=row["vt_symbol"],
        dimension_id="momentum",
        label="动量",
        weight=weight,
        score=90.0,
        reason="动量",
        row=row,
    )


def _turnover_hit(row: dict, *, weight: float = 0.20) -> DimensionHit:
    return DimensionHit(
        vt_symbol=row["vt_symbol"],
        dimension_id="turnover",
        label="换手",
        weight=weight,
        score=80.0,
        reason="换手",
        row=row,
    )


def test_run_recipe_merges_dimensions():
    momentum_rows = [
        {
            "vt_symbol": "600000.SSE",
            "symbol": "600000",
            "name": "浦发银行",
            "change_pct": 5.2,
            "turnover_rate": 1.1,
            "amount": 50_000_000,
        },
    ]
    turnover_rows = [
        {
            "vt_symbol": "600000.SSE",
            "symbol": "600000",
            "name": "浦发银行",
            "change_pct": 5.2,
            "turnover_rate": 3.5,
            "amount": 50_000_000,
        },
    ]

    def fake_run_dimension(spec, pool_size):
        if spec.dimension_id == "momentum":
            return [_momentum_hit(momentum_rows[0], weight=spec.weight)], 100
        if spec.dimension_id == "turnover":
            return [_turnover_hit(turnover_rows[0], weight=spec.weight)], 100
        return [], 0

    with patch("vnpy_ashare.screener.recipe.recipe_runner.run_dimension", side_effect=fake_run_dimension):
        result = run_recipe("intraday_multi", top_n=5)

    assert len(result.rows) == 1
    row = result.rows[0]
    assert row["vt_symbol"] == "600000.SSE"
    assert "composite_score" in row
    assert "hit_reason" in row
    assert row["source"] == "recipe"


def test_build_reason_summary():
    recipe = resolve_recipe("post_close_multi")
    assert recipe is not None
    summary = build_reason_summary(
        recipe=recipe,
        trigger="scheduled_post_close",
        row_count=3,
    )
    assert "盘后自动" in summary
    assert "命中 3 条" in summary


def test_run_recipe_parallel_dimensions():
    recipe = resolve_recipe("intraday_multi")
    assert recipe is not None
    row = {
        "vt_symbol": "600000.SSE",
        "symbol": "600000",
        "name": "浦发银行",
        "amount": 50_000_000,
    }
    with patch(
        "vnpy_ashare.screener.recipe.recipe_runner.run_parallel_map",
    ) as parallel_mock:
        parallel_mock.return_value = [
            (recipe.dimensions[0], [_momentum_hit(row)], 100),
            (recipe.dimensions[1], [], 0),
            (recipe.dimensions[2], [_turnover_hit(row)], 100),
            (recipe.dimensions[3], [], 0),
            (recipe.dimensions[4], [], 0),
        ]
        result = run_recipe("intraday_multi", top_n=5)
    parallel_mock.assert_called_once()
    assert result.rows


def test_apply_recipe_filters_excludes_st_and_low_amount():
    rows = [
        {"name": "ST测试", "amount": 100_000_000},
        {"name": "正常股份", "amount": 1_000_000},
        {"name": "活跃股份", "amount": 40_000_000},
    ]
    filtered = apply_recipe_filters(rows)
    names = [row["name"] for row in filtered]
    assert "ST测试" not in names
    assert "正常股份" not in names
    assert "活跃股份" in names


def test_apply_recipe_filters_excludes_small_total_mv():
    rows = [
        {"name": "大盘", "total_mv": 600_000},
        {"name": "小盘", "total_mv": 100_000},
    ]
    filtered = apply_recipe_filters(rows)
    names = [row["name"] for row in filtered]
    assert names == ["大盘"]
