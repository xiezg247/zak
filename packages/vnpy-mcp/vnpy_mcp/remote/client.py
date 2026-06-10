"""MCP Streamable HTTP 客户端（同步封装）。"""

from __future__ import annotations

import asyncio
import threading
from datetime import timedelta
from typing import Any

from vnpy_mcp.domain.provider import McpToolInfo


class McpClientError(Exception):
    pass


_mcp_import_lock = threading.Lock()
_mcp_sdk: tuple[Any, Any] | None = None

_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None
_loop_ready = threading.Event()
_loop_lock = threading.Lock()


def _load_mcp_sdk() -> tuple[Any, Any]:
    """线程安全加载 mcp SDK（避免 Qt 线程池并发首次 import 触发 anyio KeyError）。"""
    global _mcp_sdk
    if _mcp_sdk is not None:
        return _mcp_sdk
    with _mcp_import_lock:
        if _mcp_sdk is not None:
            return _mcp_sdk
        try:
            import anyio  # noqa: F401
            import anyio.lowlevel  # noqa: F401
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as ex:
            raise McpClientError("未安装 mcp 包，请执行：uv pip install mcp") from ex
        except KeyError as ex:
            raise McpClientError(
                "mcp/anyio 导入失败（虚拟环境可能损坏），请执行："
                "uv pip install --force-reinstall anyio mcp"
            ) from ex
        _mcp_sdk = (streamablehttp_client, ClientSession)
        return _mcp_sdk


def _loop_runner() -> None:
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _loop_ready.set()
    _loop.run_forever()


def _ensure_event_loop() -> asyncio.AbstractEventLoop:
    """后台常驻 asyncio loop，避免每次 MCP 调用 asyncio.run 重建 loop。"""
    global _loop_thread
    with _loop_lock:
        if _loop is not None and _loop.is_running():
            return _loop
        _loop_ready.clear()
        _loop_thread = threading.Thread(target=_loop_runner, name="mcp-async-loop", daemon=True)
        _loop_thread.start()
    if not _loop_ready.wait(timeout=10):
        raise McpClientError("MCP 异步事件循环启动超时")
    assert _loop is not None
    return _loop


def _run_async(coro: Any) -> Any:
    """在同步上下文中执行 async MCP 调用（提交到常驻 loop）。"""
    loop = _ensure_event_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


async def _list_tools_async(
    url: str,
    headers: dict[str, str],
    *,
    timeout: float = 30.0,
) -> list[McpToolInfo]:
    streamablehttp_client, ClientSession = _load_mcp_sdk()

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
    streamablehttp_client, ClientSession = _load_mcp_sdk()

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
    return _run_async(_call_tool_async(url, headers or {}, tool_name, arguments, timeout=timeout))
