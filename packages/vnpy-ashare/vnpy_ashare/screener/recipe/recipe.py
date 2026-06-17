"""多维度选股配方（Recipe）定义。

``TriggerKind``：``intraday`` 盘中多因子 / ``post_close`` 盘后多因子。
内置配方见 ``BUILTIN_RECIPES``；用户配方经 ``recipe_store`` 持久化。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from vnpy_ashare.screener.recipe.recipe_store import get_saved_recipe, list_saved_recipes

TriggerKind = Literal["intraday", "post_close"]

RECIPE_INTRADAY_MULTI = "intraday_multi"
RECIPE_INTRADAY_AGGRESSIVE = "intraday_aggressive"
RECIPE_ULTRA_SHORT_LIMIT = "ultra_short_limit"
RECIPE_ULTRA_SHORT_FIRST_BOARD = "ultra_short_first_board"
RECIPE_CM20_ELASTIC = "cm20_elastic"
RECIPE_EMOTION_GATE_ONLY = "emotion_gate_only"
RECIPE_POST_CLOSE_MULTI = "post_close_multi"


@dataclass(frozen=True)
class DimensionSpec:
    """配方内单个因子维度（权重参与 composite_score 加权）。"""

    dimension_id: str
    label: str
    weight: float


@dataclass(frozen=True)
class ScreenRecipe:
    """多因子选股配方；``min_dimensions`` 为命中维度数下限。"""

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
    """配方目录项（内置 / 用户保存）。"""

    recipe_id: str
    display_name: str
    trigger_kind: TriggerKind
    builtin: bool


DIMENSION_CATALOG: dict[str, dict[str, Any]] = {
    "momentum": {"label": "动量", "trigger_kinds": ("intraday", "post_close")},
    "turnover": {"label": "换手", "trigger_kinds": ("intraday",)},
    "volume_ratio": {"label": "量比", "trigger_kinds": ("intraday",)},
    "volume_surge": {"label": "放量", "trigger_kinds": ("intraday",)},
    "sector_strength": {"label": "板块", "trigger_kinds": ("intraday",)},
    "concept_strength": {"label": "概念", "trigger_kinds": ("intraday",)},
    "intraday_breakout": {"label": "突破", "trigger_kinds": ("intraday",)},
    "moneyflow_intraday": {"label": "盘中资金", "trigger_kinds": ("intraday",)},
    "sentiment_gate": {"label": "环境", "trigger_kinds": ("intraday",)},
    "limit_board": {"label": "连板涨停", "trigger_kinds": ("intraday",)},
    "first_board": {"label": "首板", "trigger_kinds": ("intraday",)},
    "cm20_elastic": {"label": "20cm弹性", "trigger_kinds": ("intraday",)},
    "moneyflow": {"label": "资金", "trigger_kinds": ("post_close",)},
    "low_pe": {"label": "估值", "trigger_kinds": ("post_close",)},
}

BUILTIN_RECIPES: dict[str, ScreenRecipe] = {
    RECIPE_INTRADAY_MULTI: ScreenRecipe(
        recipe_id=RECIPE_INTRADAY_MULTI,
        name="盘中多因子",
        trigger_kind="intraday",
        dimensions=(
            DimensionSpec("momentum", "动量", 0.28),
            DimensionSpec("volume_ratio", "量比", 0.23),
            DimensionSpec("sector_strength", "板块", 0.18),
            DimensionSpec("concept_strength", "概念", 0.08),
            DimensionSpec("turnover", "换手", 0.14),
            DimensionSpec("volume_surge", "放量", 0.09),
        ),
        top_n=20,
        pool_size=80,
        min_dimensions=2,
    ),
    RECIPE_INTRADAY_AGGRESSIVE: ScreenRecipe(
        recipe_id=RECIPE_INTRADAY_AGGRESSIVE,
        name="盘中激进",
        trigger_kind="intraday",
        dimensions=(
            DimensionSpec("momentum", "动量", 0.25),
            DimensionSpec("volume_ratio", "量比", 0.20),
            DimensionSpec("intraday_breakout", "突破", 0.15),
            DimensionSpec("moneyflow_intraday", "盘中资金", 0.15),
            DimensionSpec("concept_strength", "概念", 0.10),
            DimensionSpec("sector_strength", "板块", 0.10),
            DimensionSpec("turnover", "换手", 0.05),
        ),
        top_n=20,
        pool_size=80,
        min_dimensions=3,
    ),
    RECIPE_ULTRA_SHORT_LIMIT: ScreenRecipe(
        recipe_id=RECIPE_ULTRA_SHORT_LIMIT,
        name="极致短线·涨停",
        trigger_kind="intraday",
        dimensions=(
            DimensionSpec("limit_board", "连板涨停", 0.35),
            DimensionSpec("sector_strength", "板块", 0.25),
            DimensionSpec("turnover", "换手", 0.20),
            DimensionSpec("concept_strength", "概念", 0.12),
            DimensionSpec("sentiment_gate", "环境", 0.08),
        ),
        top_n=15,
        pool_size=60,
        min_dimensions=2,
    ),
    RECIPE_ULTRA_SHORT_FIRST_BOARD: ScreenRecipe(
        recipe_id=RECIPE_ULTRA_SHORT_FIRST_BOARD,
        name="极致短线·首板",
        trigger_kind="intraday",
        dimensions=(
            DimensionSpec("first_board", "首板", 0.40),
            DimensionSpec("concept_strength", "概念", 0.25),
            DimensionSpec("sector_strength", "板块", 0.20),
            DimensionSpec("turnover", "换手", 0.15),
        ),
        top_n=12,
        pool_size=50,
        min_dimensions=2,
    ),
    RECIPE_CM20_ELASTIC: ScreenRecipe(
        recipe_id=RECIPE_CM20_ELASTIC,
        name="20cm·弹性",
        trigger_kind="intraday",
        dimensions=(
            DimensionSpec("cm20_elastic", "20cm弹性", 0.45),
            DimensionSpec("concept_strength", "概念", 0.35),
            DimensionSpec("turnover", "换手", 0.20),
        ),
        top_n=15,
        pool_size=50,
        min_dimensions=2,
    ),
    RECIPE_EMOTION_GATE_ONLY: ScreenRecipe(
        recipe_id=RECIPE_EMOTION_GATE_ONLY,
        name="情绪观察",
        trigger_kind="intraday",
        dimensions=(
            DimensionSpec("momentum", "动量", 0.40),
            DimensionSpec("sector_strength", "板块", 0.35),
            DimensionSpec("sentiment_gate", "环境", 0.25),
        ),
        top_n=3,
        pool_size=60,
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
    """列出指定触发类型可用的维度 id。"""
    return [dim_id for dim_id, meta in DIMENSION_CATALOG.items() if trigger_kind in meta["trigger_kinds"]]


def recipe_to_config(recipe: ScreenRecipe) -> dict[str, Any]:
    """将 ``ScreenRecipe`` 转为 UI / 持久化用的 config dict。"""
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


def compute_equal_weights(enabled_ids: list[str], *, decimals: int = 2) -> dict[str, float]:
    """为启用的维度计算均等权重，总和精确为 1.0。"""
    if not enabled_ids:
        return {}
    n = len(enabled_ids)
    total_units = 10**decimals
    base_units = total_units // n
    remainder_units = total_units - base_units * n
    weights: dict[str, float] = {}
    for index, dim_id in enumerate(enabled_ids):
        units = base_units + (1 if index < remainder_units else 0)
        weights[dim_id] = units / total_units
    return weights


def normalize_recipe_config(config: dict[str, Any]) -> dict[str, Any]:
    """校验并归一化配方 config：启用维度权重之和归一化为 1，裁剪 top_n / pool_size。"""
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
    """从 config dict 构造 ``ScreenRecipe``；至少须有一个启用维度。"""
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
    """按 id 解析配方：先查内置，再查用户保存；config 非法时返回 None。"""
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


def list_recipe_ids(*, trigger_kind: TriggerKind | None = None) -> list[str]:
    """列出配方 id；可按 trigger_kind 过滤。"""
    return [entry.recipe_id for entry in list_recipe_catalog(trigger_kind=trigger_kind)]


def list_recipe_catalog(*, trigger_kind: TriggerKind | None = None) -> list[RecipeCatalogEntry]:
    """内置 + 用户配方目录（含展示名前缀「内置 · / 我的 ·」）。"""
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
    """返回指定触发类型的内置配方默认 config（新建用户配方时用）。"""
    if trigger_kind == "intraday":
        recipe = BUILTIN_RECIPES[RECIPE_INTRADAY_MULTI]
    else:
        recipe = BUILTIN_RECIPES[RECIPE_POST_CLOSE_MULTI]
    return recipe_to_config(recipe)


def _dimension_label(dimension_id: str) -> str:
    meta = DIMENSION_CATALOG.get(dimension_id, {})
    return str(meta.get("label") or dimension_id)
