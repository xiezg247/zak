"""通达信 MCP 连接状态（AnalysisService.bind_mcp 写入）。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

McpExecute = Callable[[str, dict[str, Any]], str]


@dataclass
class McpBinding:
    execute: McpExecute | None = None
    tool_names: list[str] = field(default_factory=list)
