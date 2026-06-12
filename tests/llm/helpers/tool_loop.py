"""测试用非流式 tool loop（生产路径已统一走 graph/runner）。"""

from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from vnpy_llm.chat.client import LlmClientError, create_openai_client
from vnpy_llm.config.settings import LlmConfig
from vnpy_llm.tools.result import enrich_tool_result


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


def _run_tool_call_safe(
    tool_executor: Callable[[str, dict[str, Any]], str],
    name: str,
    arguments: dict[str, Any],
) -> str:
    try:
        result = tool_executor(name, arguments)
    except Exception as ex:
        result = json.dumps({"error": str(ex)}, ensure_ascii=False)
    return enrich_tool_result(result)


def execute_tool_calls_parallel(
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
        result = _run_tool_call_safe(
            tool_executor,
            fn.name,
            _parse_tool_arguments(fn.arguments),
        )
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
            indexed.append((index, call, enrich_tool_result(result)))

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
            pairs = execute_tool_calls_parallel(tool_calls, tool_executor)
        else:
            pairs = [
                (
                    call,
                    _run_tool_call_safe(
                        tool_executor,
                        call.function.name,
                        _parse_tool_arguments(call.function.arguments),
                    ),
                )
                for call in tool_calls
            ]
        _append_tool_results(working, pairs)

    raise LlmClientError("工具调用轮次超过上限")
