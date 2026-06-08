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
        summary="官方 Streamable HTTP MCP：A 股实时行情、K 线、板块、F10 等。",
        env_vars=("mcp/",),
        tags=("行情", "K 线", "通达信", "MCP"),
    ),
}


def format_mcp_prompt(enabled: list[str]) -> str:
    """兼容 LlmEngine：实际 prompt 由 McpEngine.build_mcp_prompt() 生成。"""
    if not enabled:
        return ""
    lines = ["【已启用 MCP】"]
    for name in enabled:
        meta = BUILTIN_MCP_PROVIDERS.get(name)
        if meta:
            lines.append(f"- {meta.title}（{name}）：{meta.summary}")
        else:
            lines.append(f"- {name}")
    return "\n".join(lines)
