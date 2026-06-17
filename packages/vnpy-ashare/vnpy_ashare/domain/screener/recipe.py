"""选股配方领域模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from vnpy_common.domain.base import FrozenModel

TriggerKind = Literal["intraday", "post_close"]

RECIPE_INTRADAY_MULTI = "intraday_multi"
RECIPE_INTRADAY_AGGRESSIVE = "intraday_aggressive"
RECIPE_ULTRA_SHORT_LIMIT = "ultra_short_limit"
RECIPE_ULTRA_SHORT_FIRST_BOARD = "ultra_short_first_board"
RECIPE_CM20_ELASTIC = "cm20_elastic"
RECIPE_EMOTION_GATE_ONLY = "emotion_gate_only"
RECIPE_POST_CLOSE_MULTI = "post_close_multi"


class DimensionSpec(FrozenModel):
    """配方内单个因子维度（权重参与 composite_score 加权）。"""

    dimension_id: str = Field(description="维度标识")
    label: str = Field(description="维度展示名")
    weight: float = Field(description="维度权重")


class ScreenRecipe(FrozenModel):
    """多因子选股配方；``min_dimensions`` 为命中维度数下限。"""

    recipe_id: str = Field(description="配方 id")
    name: str = Field(description="配方名称")
    trigger_kind: TriggerKind = Field(description="触发类型（盘中/盘后）")
    dimensions: tuple[DimensionSpec, ...] = Field(description="维度规格列表")
    top_n: int = Field(default=20, description="返回条数上限")
    pool_size: int = Field(default=50, description="候选池大小")
    min_dimensions: int = Field(default=1, description="最低命中维度数")
    builtin: bool = Field(default=True, description="是否为内置配方")


class RecipeCatalogEntry(FrozenModel):
    """配方目录项（内置 / 用户保存）。"""

    recipe_id: str = Field(description="配方 id")
    display_name: str = Field(description="展示名称")
    trigger_kind: TriggerKind = Field(description="触发类型（盘中/盘后）")
    builtin: bool = Field(description="是否为内置配方")
