"""多因子配方权重计算测试。"""

from __future__ import annotations

from vnpy_ashare.screener.recipe.recipe import compute_equal_weights, normalize_recipe_config


def test_compute_equal_weights_divides_evenly():
    weights = compute_equal_weights(["a", "b", "c", "d", "e"])
    assert weights == {
        "a": 0.2,
        "b": 0.2,
        "c": 0.2,
        "d": 0.2,
        "e": 0.2,
    }
    assert abs(sum(weights.values()) - 1.0) < 1e-9


def test_compute_equal_weights_handles_indivisible_count():
    weights = compute_equal_weights(["a", "b", "c"])
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert sorted(weights.values()) == [0.33, 0.33, 0.34]


def test_normalize_recipe_config_preserves_manual_edits():
    config = normalize_recipe_config(
        {
            "dimensions": [
                {"dimension_id": "momentum", "enabled": True, "weight": 0.6},
                {"dimension_id": "turnover", "enabled": True, "weight": 0.2},
                {"dimension_id": "volume_ratio", "enabled": False, "weight": 0.0},
            ]
        }
    )
    enabled = [item for item in config["dimensions"] if item["enabled"]]
    assert enabled[0]["weight"] == 0.75
    assert enabled[1]["weight"] == 0.25
