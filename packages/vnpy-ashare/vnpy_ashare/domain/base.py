"""Pydantic 领域模型基类。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    """不可变领域模型。"""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
    )


class MutableModel(BaseModel):
    """可变数据载体。"""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )
