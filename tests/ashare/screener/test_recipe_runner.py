"""多维度选股配方执行测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.screener.recipe import resolve_recipe
from vnpy_ashare.screener.recipe_runner import _DimensionHit, build_reason_summary, run_recipe


def test_run_recipe_merges_dimensions():
    momentum_rows = [
        {
            "vt_symbol": "600000.SSE",
            "symbol": "600000",
            "name": "浦发银行",
            "change_pct": 5.2,
            "turnover_rate": 1.1,
        },
        {
            "vt_symbol": "600001.SSE",
            "symbol": "600001",
            "name": "邯郸钢铁",
            "change_pct": 4.8,
            "turnover_rate": 0.8,
        },
    ]
    turnover_rows = [
        {
            "vt_symbol": "600000.SSE",
            "symbol": "600000",
            "name": "浦发银行",
            "change_pct": 5.2,
            "turnover_rate": 3.5,
        },
    ]

    with patch(
        "vnpy_ashare.screener.recipe_runner._dimension_momentum",
        return_value=(
            [
                _DimensionHit(
                    vt_symbol="600000.SSE",
                    dimension_id="momentum",
                    label="动量",
                    weight=0.55,
                    score=90.0,
                    reason="动量：涨幅 +5.20%，排名第 1",
                    row=momentum_rows[0],
                ),
            ],
            100,
        ),
    ):
        with patch(
            "vnpy_ashare.screener.recipe_runner._dimension_turnover",
            return_value=(
                [
                    _DimensionHit(
                        vt_symbol="600000.SSE",
                        dimension_id="turnover",
                        label="换手",
                        weight=0.45,
                        score=80.0,
                        reason="换手：3.50%，排名第 1",
                        row=turnover_rows[0],
                    ),
                ],
                100,
            ),
        ):
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
    with patch(
        "vnpy_ashare.screener.recipe_runner.run_parallel_map",
    ) as parallel_mock:
        parallel_mock.return_value = [
            (
                recipe.dimensions[0],
                [
                    _DimensionHit(
                        vt_symbol="600000.SSE",
                        dimension_id="momentum",
                        label="动量",
                        weight=0.55,
                        score=90.0,
                        reason="动量",
                        row={"vt_symbol": "600000.SSE", "symbol": "600000", "name": "浦发银行"},
                    )
                ],
                100,
            ),
            (
                recipe.dimensions[1],
                [],
                0,
            ),
        ]
        result = run_recipe("intraday_multi", top_n=5)
    parallel_mock.assert_called_once()
    assert result.rows
