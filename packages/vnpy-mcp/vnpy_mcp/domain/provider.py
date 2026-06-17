"""MCP Provider 基类（对标 vnpy_skills.domain.SkillTemplate）。"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from pydantic import Field

from vnpy_common.domain.base import MutableModel
from vnpy_skills.domain import ToolSpec


class McpToolInfo(MutableModel):
    """远端 MCP 工具元数据。"""

    name: str = Field(description="工具名称")
    description: str = Field(default="", description="工具说明")
    input_schema: dict[str, Any] = Field(default_factory=dict, description="JSON Schema 参数")


class McpProvider(ABC):
    """
    远端 MCP 服务 Provider。

    子类定义 provider_name、description，并实现 connect 配置。
    工具列表由 MCP 服务端动态发现，无需手写 register_tools。
    """

    provider_name: str = ""
    author: str = "zak"
    description: str = ""

    def __init__(self) -> None:
        self._tools: list[McpToolInfo] = []
        self._connected = False

    def on_init(self) -> None:
        """初始化（检查 API Key 等）。"""
        pass

    @property
    @abstractmethod
    def available(self) -> bool:
        """Provider 是否可用（如缺少 API Key 则不可用）。"""

    @property
    @abstractmethod
    def url(self) -> str:
        """MCP Streamable HTTP 端点。"""

    @property
    @abstractmethod
    def headers(self) -> dict[str, str]:
        """请求头（如 tdx-api-key）。"""

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def tools(self) -> list[McpToolInfo]:
        return list(self._tools)

    def tool_prefix(self) -> str:
        """OpenAI 工具名前缀，避免多 Provider 冲突。"""
        return f"mcp_{self.provider_name}_"

    def prefixed_name(self, tool_name: str) -> str:
        return f"{self.tool_prefix()}{tool_name}"

    def strip_prefix(self, prefixed: str) -> str | None:
        prefix = self.tool_prefix()
        if not prefixed.startswith(prefix):
            return None
        return prefixed[len(prefix) :]

    def set_tools(self, tools: list[McpToolInfo]) -> None:
        self._tools = list(tools)
        self._connected = True

    def mark_disconnected(self) -> None:
        self._tools.clear()
        self._connected = False

    def to_tool_specs(self) -> list[ToolSpec]:
        specs: list[ToolSpec] = []
        for tool in self._tools:
            params = tool.input_schema or {"type": "object", "properties": {}}
            specs.append(
                ToolSpec(
                    name=self.prefixed_name(tool.name),
                    description=f"[{self.provider_name}] {tool.description}".strip(),
                    parameters=params,
                )
            )
        return specs

    def prompt_section(self) -> str:
        lines = [
            f"### MCP: {self.provider_name}",
            self.description,
        ]
        if self._tools:
            lines.append("可用工具：")
            for tool in self._tools[:12]:
                lines.append(f"- {tool.name}: {tool.description}")
            if len(self._tools) > 12:
                lines.append(f"... 共 {len(self._tools)} 个工具")
        return "\n".join(lines)

    @staticmethod
    def format_tool_result(result: Any) -> str:
        """将 MCP call_tool 结果序列化为 LLM 可读字符串。"""
        content = getattr(result, "content", None)
        if content is None:
            return json.dumps(result, ensure_ascii=False, default=str)

        parts: list[str] = []
        for block in content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
                continue
            data = getattr(block, "data", None)
            if data is not None:
                parts.append(json.dumps(data, ensure_ascii=False, default=str))
                continue
            mime = getattr(block, "mimeType", None) or getattr(block, "mime_type", None)
            if mime:
                parts.append(f"[{mime} content omitted]")
        if parts:
            return "\n".join(parts)
        if getattr(result, "isError", False) or getattr(result, "is_error", False):
            return json.dumps({"error": "MCP tool returned error"}, ensure_ascii=False)
        return json.dumps({"result": str(result)}, ensure_ascii=False, default=str)
