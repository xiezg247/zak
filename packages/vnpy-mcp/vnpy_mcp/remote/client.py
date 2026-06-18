"""MCP Streamable HTTP 客户端（同步封装）。"""

from __future__ import annotations

import asyncio
import threading
from datetime import timedelta
from typing import Any, cast

from vnpy_mcp.domain.provider import McpToolInfo


class McpClientError(Exception):
    pass


_NETWORK_ERROR_NAMES = frozenset(
    {"ConnectError", "ConnectTimeout", "ReadTimeout", "WriteTimeout", "TimeoutException"}
)
_STREAM_ERROR_NAMES = frozenset({"BrokenResourceError", "ClosedResourceError"})


def _iter_exceptions(exc: BaseException) -> Any:
    """深度优先遍历异常链与 ExceptionGroup。"""
    yield exc
    nested = getattr(exc, "exceptions", None)
    if nested:
        for sub in nested:
            yield from _iter_exceptions(sub)
    cause = exc.__cause__
    if cause is not None and cause is not exc:
        yield from _iter_exceptions(cause)
    context = exc.__context__
    if context is not None and context is not exc and context is not cause:
        yield from _iter_exceptions(context)


def _friendly_client_error(exc: BaseException) -> str:
    network_hit = False
    stream_hit = False
    root = exc
    for item in _iter_exceptions(exc):
        root = item
        if isinstance(item, McpClientError):
            return str(item)
        type_name = type(item).__name__
        if type_name in _NETWORK_ERROR_NAMES:
            network_hit = True
        if type_name in _STREAM_ERROR_NAMES:
            stream_hit = True
    if network_hit:
        return "无法连接 MCP 服务（网络或 TLS 失败），请检查网络与 mcp/mcp.json 中的 URL/API Key"
    if stream_hit:
        return "MCP 连接已中断（远端未响应或 TLS 握手失败）"
    message = str(root).strip()
    if message:
        return message[:240]
    return type(root).__name__


_mcp_import_lock = threading.Lock()
_mcp_sdk: tuple[Any, Any] | None = None

_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None
_loop_ready = threading.Event()
_loop_lock = threading.Lock()
# Streamable HTTP 客户端不支持同一 loop 上并发建连，否则易触发 TLS/ConnectError。
_mcp_call_lock = threading.Lock()


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
            from mcp.client.streamable_http import streamablehttp_client

            from mcp import ClientSession
        except ImportError as ex:
            raise McpClientError("未安装 mcp 包，请执行：uv pip install mcp") from ex
        except KeyError as ex:
            raise McpClientError("mcp/anyio 导入失败（虚拟环境可能损坏），请执行：uv pip install --force-reinstall anyio mcp") from ex
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
    with _mcp_call_lock:
        loop = _ensure_event_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result()
        except Exception as ex:
            raise McpClientError(_friendly_client_error(ex)) from ex


def _is_retriable_network_error(exc: BaseException) -> bool:
    for item in _iter_exceptions(exc):
        if type(item).__name__ in _NETWORK_ERROR_NAMES | _STREAM_ERROR_NAMES:
            return True
    return False


async def _with_retry(coro_factory: Any, *, attempts: int = 3, base_delay: float = 0.25) -> Any:
    last_exc: BaseException | None = None
    for attempt in range(attempts):
        try:
            return await coro_factory()
        except Exception as ex:
            last_exc = ex
            if not _is_retriable_network_error(ex) or attempt + 1 >= attempts:
                raise
            await asyncio.sleep(base_delay * (attempt + 1))
    assert last_exc is not None
    raise last_exc


async def _list_tools_async(
    url: str,
    headers: dict[str, str],
    *,
    timeout: float = 30.0,
) -> list[McpToolInfo]:
    async def _once() -> list[McpToolInfo]:
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

    return await _with_retry(_once)


async def _call_tool_async(
    url: str,
    headers: dict[str, str],
    tool_name: str,
    arguments: dict[str, Any],
    *,
    timeout: float = 60.0,
) -> Any:
    async def _once() -> Any:
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

    return await _with_retry(_once)


def list_remote_tools(
    url: str,
    headers: dict[str, str] | None = None,
    *,
    timeout: float = 30.0,
) -> list[McpToolInfo]:
    return cast(list[McpToolInfo], _run_async(_list_tools_async(url, headers or {}, timeout=timeout)))


def call_remote_tool(
    url: str,
    headers: dict[str, str] | None,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    timeout: float = 60.0,
) -> Any:
    return _run_async(_call_tool_async(url, headers or {}, tool_name, arguments, timeout=timeout))
