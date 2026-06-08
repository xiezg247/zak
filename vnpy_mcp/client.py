"""MCP Streamable HTTP 客户端（同步封装）。"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from vnpy_mcp.base import McpToolInfo


class McpClientError(Exception):
    pass


def _run_async(coro: Any) -> Any:
    """在同步上下文中执行 async MCP 调用。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Qt / 已有事件循环：在新线程中跑独立 loop
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def _list_tools_async(
    url: str,
    headers: dict[str, str],
    *,
    timeout: float = 30.0,
) -> list[McpToolInfo]:
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except ImportError as ex:
        raise McpClientError(
            "未安装 mcp 包，请执行：uv pip install mcp"
        ) from ex

    timeout_delta = timedelta(seconds=timeout)
    async with streamablehttp_client(
        url,
        headers=headers or None,
        timeout=timeout_delta,
        sse_read_timeout=timeout_delta,
        terminate_on_close=True,
    ) as (read, write, _session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            tools: list[McpToolInfo] = []
            for tool in result.tools:
                schema = tool.inputSchema or {"type": "object", "properties": {}}
                tools.append(
                    McpToolInfo(
                        name=tool.name,
                        description=tool.description or "",
                        input_schema=dict(schema),
                    )
                )
            return tools


async def _call_tool_async(
    url: str,
    headers: dict[str, str],
    tool_name: str,
    arguments: dict[str, Any],
    *,
    timeout: float = 60.0,
) -> Any:
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except ImportError as ex:
        raise McpClientError(
            "未安装 mcp 包，请执行：uv pip install mcp"
        ) from ex

    timeout_delta = timedelta(seconds=timeout)
    async with streamablehttp_client(
        url,
        headers=headers or None,
        timeout=timeout_delta,
        sse_read_timeout=timeout_delta,
        terminate_on_close=True,
    ) as (read, write, _session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool_name, arguments)


def list_remote_tools(
    url: str,
    headers: dict[str, str] | None = None,
    *,
    timeout: float = 30.0,
) -> list[McpToolInfo]:
    return _run_async(_list_tools_async(url, headers or {}, timeout=timeout))


def call_remote_tool(
    url: str,
    headers: dict[str, str] | None,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    timeout: float = 60.0,
) -> Any:
    return _run_async(
        _call_tool_async(url, headers or {}, tool_name, arguments, timeout=timeout)
    )
