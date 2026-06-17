"""通达信 MCP 连接状态（AnalysisService.bind_mcp 写入）。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import Field

from vnpy_ashare.domain.base import MutableModel

McpExecute = Callable[[str, dict[str, Any]], str]


class McpBinding(MutableModel):
    execute: McpExecute | None = Field(default=None, description="execute")
    tool_names: list[str] = Field(default_factory=list, description="tool names")
