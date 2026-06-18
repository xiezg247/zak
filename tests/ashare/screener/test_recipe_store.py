"""选股配方持久化测试。"""

from __future__ import annotations

import vnpy_ashare.screener.recipe.recipe_store as recipe_store
from vnpy_ashare.screener.recipe.recipe import (
    list_recipe_catalog,
    normalize_recipe_config,
    resolve_recipe,
    screen_recipe_from_config,
)


def test_save_and_resolve_custom_recipe(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setattr(recipe_store, "get_app_db_path", lambda settings=None: db_path)

    config = normalize_recipe_config(
        {
            "top_n": 15,
            "pool_size": 40,
            "min_dimensions": 1,
            "dimensions": [
                {"dimension_id": "momentum", "label": "动量", "weight": 0.6, "enabled": True},
                {"dimension_id": "turnover", "label": "换手", "weight": 0.4, "enabled": True},
            ],
        }
    )
    saved = recipe_store.save_recipe(
        "我的盘中",
        trigger_kind="intraday",
        config=config,
    )
    assert saved.id

    recipe = resolve_recipe(saved.id)
    assert recipe is not None
    assert recipe.name == "我的盘中"
    assert recipe.top_n == 15
    assert len(recipe.dimensions) == 2
    assert recipe.builtin is False

    catalog = list_recipe_catalog(trigger_kind="intraday")
    ids = [entry.recipe_id for entry in catalog]
    assert "intraday_multi" in ids
    assert saved.id in ids


def test_screen_recipe_from_config_normalizes_weights():
    recipe = screen_recipe_from_config(
        recipe_id="preview",
        name="预览",
        trigger_kind="post_close",
        config={
            "top_n": 10,
            "dimensions": [
                {"dimension_id": "moneyflow", "enabled": True, "weight": 2},
                {"dimension_id": "low_pe", "enabled": True, "weight": 2},
            ],
        },
        builtin=False,
    )
    weight_sum = sum(spec.weight for spec in recipe.dimensions)
    assert abs(weight_sum - 1.0) < 1e-6
