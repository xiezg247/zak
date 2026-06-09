"""多维度选股配方（Recipe）定义。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TriggerKind = Literal["intraday", "post_close"]

RECIPE_INTRADAY_MULTI = "intraday_multi"
RECIPE_POST_CLOSE_MULTI = "post_close_multi"


@dataclass(frozen=True)
class DimensionSpec:
    dimension_id: str
    label: str
    weight: float


@dataclass(frozen=True)
class ScreenRecipe:
    recipe_id: str
    name: str
    trigger_kind: TriggerKind
    dimensions: tuple[DimensionSpec, ...]
    top_n: int = 20
    pool_size: int = 50
    min_dimensions: int = 1


BUILTIN_RECIPES: dict[str, ScreenRecipe] = {
    RECIPE_INTRADAY_MULTI: ScreenRecipe(
        recipe_id=RECIPE_INTRADAY_MULTI,
        name="盘中多因子",
        trigger_kind="intraday",
        dimensions=(
            DimensionSpec("momentum", "动量", 0.55),
            DimensionSpec("turnover", "换手", 0.45),
        ),
        top_n=20,
        pool_size=50,
        min_dimensions=1,
    ),
    RECIPE_POST_CLOSE_MULTI: ScreenRecipe(
        recipe_id=RECIPE_POST_CLOSE_MULTI,
        name="盘后多因子",
        trigger_kind="post_close",
        dimensions=(
            DimensionSpec("moneyflow", "资金", 0.45),
            DimensionSpec("low_pe", "估值", 0.35),
            DimensionSpec("momentum", "动量", 0.20),
        ),
        top_n=20,
        pool_size=50,
        min_dimensions=1,
    ),
}


def get_recipe(recipe_id: str) -> ScreenRecipe | None:
    return BUILTIN_RECIPES.get(recipe_id.strip())


def list_recipe_ids(*, trigger_kind: TriggerKind | None = None) -> list[str]:
    if trigger_kind is None:
        return list(BUILTIN_RECIPES.keys())
    return [
        item.recipe_id
        for item in BUILTIN_RECIPES.values()
        if item.trigger_kind == trigger_kind
    ]
