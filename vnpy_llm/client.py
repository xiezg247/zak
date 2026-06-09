"""OpenAI 兼容流式客户端。"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from vnpy_llm.config import LlmConfig


class LlmClientError(Exception):
    pass


@dataclass
class _StreamingToolCall:
    id: str = ""
    name: str = ""
    arguments: str = ""
    type: str = "function"


def create_openai_client(config: LlmConfig) -> Any:
    if not config.configured:
        raise LlmClientError("未配置 LLM_API_KEY，请在 .env 中设置")
    try:
        from openai import OpenAI
    except ImportError as ex:
        raise LlmClientError("未安装 openai 包，请执行：uv pip install openai") from ex
    return OpenAI(api_key=config.api_key, base_url=config.api_base)


def stream_chat_completion(
    config: LlmConfig,
    messages: list[dict[str, str]],
) -> Iterator[str]:
    client = create_openai_client(config)
    try:
        stream = client.chat.completions.create(
            model=config.model,
            messages=messages,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            stream=True,
        )
    except Exception as ex:
        raise LlmClientError(str(ex)) from ex

    for chunk in stream:
        delta = _extract_delta(chunk)
        if delta:
            yield delta


def _parse_tool_arguments(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}


def _tool_call_payload(call: Any) -> dict[str, Any]:
    fn = call.function
    return {
        "id": call.id,
        "type": getattr(call, "type", None) or "function",
        "function": {
            "name": fn.name,
            "arguments": fn.arguments,
        },
    }


def _execute_tool_calls_parallel(
    tool_calls: list[Any],
    tool_executor: Callable[[str, dict[str, Any]], str],
    *,
    max_workers: int = 4,
) -> list[tuple[Any, str]]:
    """并行执行同一轮内的多个 tool call，保持原始顺序返回。"""
    if not tool_calls:
        return []
    if len(tool_calls) == 1:
        call = tool_calls[0]
        fn = call.function
        result = tool_executor(fn.name, _parse_tool_arguments(fn.arguments))
        return [(call, result)]

    indexed: list[tuple[int, Any, str]] = []
    workers = min(len(tool_calls), max_workers)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {}
        for index, call in enumerate(tool_calls):
            fn = call.function
            future = pool.submit(
                tool_executor,
                fn.name,
                _parse_tool_arguments(fn.arguments),
            )
            future_map[future] = (index, call)

        for future in as_completed(future_map):
            index, call = future_map[future]
            try:
                result = future.result()
            except Exception as ex:
                result = json.dumps({"error": str(ex)}, ensure_ascii=False)
            indexed.append((index, call, result))

    indexed.sort(key=lambda item: item[0])
    return [(call, result) for _, call, result in indexed]


def _append_tool_results(
    working: list[dict[str, Any]],
    pairs: list[tuple[Any, str]],
) -> None:
    for call, result in pairs:
        working.append(
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": result,
            }
        )


def complete_with_tools(
    config: LlmConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], str],
    *,
    max_rounds: int = 5,
    parallel_tool_calls: bool = True,
) -> tuple[str, list[dict[str, Any]]]:
    """带工具调用的多轮对话，返回最终回复与更新后的 messages。"""
    client = create_openai_client(config)
    working = list(messages)

    for _ in range(max_rounds):
        kwargs: dict[str, Any] = {
            "model": config.model,
            "messages": working,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
        }
        if tools:
            kwargs["tools"] = tools

        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as ex:
            raise LlmClientError(str(ex)) from ex

        choice = response.choices[0]
        message = choice.message
        tool_calls = getattr(message, "tool_calls", None) or []

        if not tool_calls:
            content = (message.content or "").strip()
            working.append({"role": "assistant", "content": content})
            return content, working

        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [_tool_call_payload(call) for call in tool_calls],
        }
        working.append(assistant_msg)

        if parallel_tool_calls:
            pairs = _execute_tool_calls_parallel(tool_calls, tool_executor)
        else:
            pairs = [
                (call, tool_executor(call.function.name, _parse_tool_arguments(call.function.arguments)))
                for call in tool_calls
            ]
        _append_tool_results(working, pairs)

    raise LlmClientError("工具调用轮次超过上限")


def stream_with_tools(
    config: LlmConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], str],
    *,
    max_rounds: int = 5,
    parallel_tool_calls: bool = True,
) -> Iterator[str]:
    """带工具调用的真流式对话，逐 token 产出最终回复文本。"""
    client = create_openai_client(config)
    working = list(messages)

    for _ in range(max_rounds):
        kwargs: dict[str, Any] = {
            "model": config.model,
            "messages": working,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools

        try:
            stream = client.chat.completions.create(**kwargs)
        except Exception as ex:
            raise LlmClientError(str(ex)) from ex

        content_parts: list[str] = []
        tool_calls_acc: dict[int, _StreamingToolCall] = {}
        finish_reason: str | None = None

        for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            finish_reason = choice.finish_reason or finish_reason
            delta = choice.delta

            if delta.content:
                content_parts.append(delta.content)
                yield delta.content

            for tc in delta.tool_calls or []:
                acc = tool_calls_acc.setdefault(tc.index, _StreamingToolCall())
                if tc.id:
                    acc.id = tc.id
                if tc.type:
                    acc.type = tc.type
                if tc.function:
                    if tc.function.name:
                        acc.name += tc.function.name
                    if tc.function.arguments:
                        acc.arguments += tc.function.arguments

        if tool_calls_acc:
            ordered = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": "".join(content_parts),
                "tool_calls": [
                    {
                        "id": item.id,
                        "type": item.type,
                        "function": {
                            "name": item.name,
                            "arguments": item.arguments,
                        },
                    }
                    for item in ordered
                ],
            }
            working.append(assistant_msg)

            class _CallProxy:
                def __init__(self, item: _StreamingToolCall) -> None:
                    self.id = item.id
                    self.type = item.type
                    self.function = type("Fn", (), {"name": item.name, "arguments": item.arguments})()

            proxies = [_CallProxy(item) for item in ordered]
            if parallel_tool_calls:
                pairs = _execute_tool_calls_parallel(proxies, tool_executor)
            else:
                pairs = [
                    (
                        proxy,
                        tool_executor(proxy.function.name, _parse_tool_arguments(proxy.function.arguments)),
                    )
                    for proxy in proxies
                ]
            _append_tool_results(working, pairs)
            continue

        content = "".join(content_parts).strip()
        working.append({"role": "assistant", "content": content})
        return

    raise LlmClientError("工具调用轮次超过上限")


def _extract_delta(chunk: Any) -> str:
    choices = getattr(chunk, "choices", None)
    if not choices:
        return ""
    choice = choices[0]
    delta = getattr(choice, "delta", None)
    if delta is None:
        return ""
    content = getattr(delta, "content", None)
    return content or ""
