"""OpenAI function tool schema 小工具（graph 层共用）。"""

from __future__ import annotations

from typing import Any


def openai_tool_name(tool: dict[str, Any]) -> str:
    """从 OpenAI tools 条目中取出 function name。"""
    return str((tool.get("function") or {}).get("name", "")).strip()


def filter_openai_tools(
    tools: list[dict[str, Any]],
    *,
    allowed: set[str] | None = None,
    blocked: set[str] | None = None,
) -> list[dict[str, Any]]:
    """按白名单或黑名单过滤 tools 列表。"""
    result: list[dict[str, Any]] = []
    for tool in tools:
        name = openai_tool_name(tool)
        if not name:
            continue
        if allowed is not None and name not in allowed:
            continue
        if blocked is not None and name in blocked:
            continue
        result.append(tool)
    return result
