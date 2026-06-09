"""多维度选股配方（Recipe）定义。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from vnpy_ashare.screener.recipe_store import get_saved_recipe, list_saved_recipes

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
    builtin: bool = True


@dataclass(frozen=True)
class RecipeCatalogEntry:
    recipe_id: str
    display_name: str
    trigger_kind: TriggerKind
    builtin: bool


DIMENSION_CATALOG: dict[str, dict[str, Any]] = {
    "momentum": {"label": "动量", "trigger_kinds": ("intraday", "post_close")},
    "turnover": {"label": "换手", "trigger_kinds": ("intraday",)},
    "moneyflow": {"label": "资金", "trigger_kinds": ("post_close",)},
    "low_pe": {"label": "估值", "trigger_kinds": ("post_close",)},
}

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


def list_dimension_ids(*, trigger_kind: TriggerKind) -> list[str]:
    return [dim_id for dim_id, meta in DIMENSION_CATALOG.items() if trigger_kind in meta["trigger_kinds"]]


def recipe_to_config(recipe: ScreenRecipe) -> dict[str, Any]:
    return {
        "top_n": recipe.top_n,
        "pool_size": recipe.pool_size,
        "min_dimensions": recipe.min_dimensions,
        "dimensions": [
            {
                "dimension_id": spec.dimension_id,
                "label": spec.label,
                "weight": spec.weight,
                "enabled": True,
            }
            for spec in recipe.dimensions
        ],
    }


def normalize_recipe_config(config: dict[str, Any]) -> dict[str, Any]:
    raw_dims = list(config.get("dimensions") or [])
    enabled = [item for item in raw_dims if item.get("enabled", True)]
    if not enabled:
        raise ValueError("至少启用一个维度")

    weight_sum = sum(float(item.get("weight") or 0) for item in enabled)
    if weight_sum <= 0:
        raise ValueError("维度权重之和须大于 0")

    normalized_dims: list[dict[str, Any]] = []
    for item in raw_dims:
        if not item.get("enabled", True):
            normalized_dims.append(
                {
                    "dimension_id": str(item.get("dimension_id", "")),
                    "label": str(item.get("label") or _dimension_label(str(item.get("dimension_id", "")))),
                    "weight": 0.0,
                    "enabled": False,
                }
            )
            continue
        dim_id = str(item.get("dimension_id", ""))
        normalized_dims.append(
            {
                "dimension_id": dim_id,
                "label": str(item.get("label") or _dimension_label(dim_id)),
                "weight": round(float(item.get("weight") or 0) / weight_sum, 4),
                "enabled": True,
            }
        )

    enabled_count = sum(1 for item in normalized_dims if item.get("enabled"))
    min_dimensions = int(config.get("min_dimensions") or 1)
    min_dimensions = max(1, min(min_dimensions, enabled_count))

    return {
        "top_n": max(1, min(int(config.get("top_n") or 20), 200)),
        "pool_size": max(10, min(int(config.get("pool_size") or 50), 500)),
        "min_dimensions": min_dimensions,
        "dimensions": normalized_dims,
    }


def screen_recipe_from_config(
    *,
    recipe_id: str,
    name: str,
    trigger_kind: TriggerKind,
    config: dict[str, Any],
    builtin: bool = False,
) -> ScreenRecipe:
    normalized = normalize_recipe_config(config)
    specs: list[DimensionSpec] = []
    for item in normalized["dimensions"]:
        if not item.get("enabled"):
            continue
        specs.append(
            DimensionSpec(
                dimension_id=str(item["dimension_id"]),
                label=str(item["label"]),
                weight=float(item["weight"]),
            )
        )
    if not specs:
        raise ValueError("至少启用一个维度")
    return ScreenRecipe(
        recipe_id=recipe_id,
        name=name,
        trigger_kind=trigger_kind,
        dimensions=tuple(specs),
        top_n=int(normalized["top_n"]),
        pool_size=int(normalized["pool_size"]),
        min_dimensions=int(normalized["min_dimensions"]),
        builtin=builtin,
    )


def resolve_recipe(recipe_id: str) -> ScreenRecipe | None:
    rid = recipe_id.strip()
    builtin = BUILTIN_RECIPES.get(rid)
    if builtin is not None:
        return builtin

    saved = get_saved_recipe(rid)
    if saved is None:
        return None
    try:
        return screen_recipe_from_config(
            recipe_id=saved.id,
            name=saved.name,
            trigger_kind=saved.trigger_kind,
            config=saved.config,
            builtin=False,
        )
    except ValueError:
        return None


def get_recipe(recipe_id: str) -> ScreenRecipe | None:
    return resolve_recipe(recipe_id)


def list_recipe_ids(*, trigger_kind: TriggerKind | None = None) -> list[str]:
    return [entry.recipe_id for entry in list_recipe_catalog(trigger_kind=trigger_kind)]


def list_recipe_catalog(*, trigger_kind: TriggerKind | None = None) -> list[RecipeCatalogEntry]:
    entries: list[RecipeCatalogEntry] = []
    for recipe in BUILTIN_RECIPES.values():
        if trigger_kind is not None and recipe.trigger_kind != trigger_kind:
            continue
        entries.append(
            RecipeCatalogEntry(
                recipe_id=recipe.recipe_id,
                display_name=f"内置 · {recipe.name}",
                trigger_kind=recipe.trigger_kind,
                builtin=True,
            )
        )
    for saved in list_saved_recipes(trigger_kind=trigger_kind):
        entries.append(
            RecipeCatalogEntry(
                recipe_id=saved.id,
                display_name=f"我的 · {saved.name}",
                trigger_kind=saved.trigger_kind,
                builtin=False,
            )
        )
    return entries


def default_config_for_trigger(trigger_kind: TriggerKind) -> dict[str, Any]:
    if trigger_kind == "intraday":
        recipe = BUILTIN_RECIPES[RECIPE_INTRADAY_MULTI]
    else:
        recipe = BUILTIN_RECIPES[RECIPE_POST_CLOSE_MULTI]
    return recipe_to_config(recipe)


def _dimension_label(dimension_id: str) -> str:
    meta = DIMENSION_CATALOG.get(dimension_id, {})
    return str(meta.get("label") or dimension_id)
