"""MCP 配置 Pydantic 基类。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FrozenConfigModel(BaseModel):
    """不可变 MCP 配置模型。"""

    model_config = ConfigDict(frozen=True)
