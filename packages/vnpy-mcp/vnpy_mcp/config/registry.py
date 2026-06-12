"""MCP Provider 元数据。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class McpProviderMeta:
    provider_name: str
    title: str
    summary: str
    env_vars: tuple[str, ...]
    tags: tuple[str, ...]


BUILTIN_MCP_PROVIDERS: dict[str, McpProviderMeta] = {
    "tdx": McpProviderMeta(
        provider_name="tdx",
        title="通达信 MCP",
        summary="官方 Streamable HTTP MCP：A 股实时行情、K 线、板块、研报等。",
        env_vars=("mcp/",),
        tags=("行情", "K 线", "通达信", "MCP", "研报"),
    ),
}
