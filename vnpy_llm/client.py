"""OpenAI 兼容流式客户端。"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

from vnpy_llm.config import LlmConfig


class LlmClientError(Exception):
    pass


def stream_chat_completion(
    config: LlmConfig,
    messages: list[dict[str, str]],
) -> Iterator[str]:
    if not config.configured:
        raise LlmClientError("未配置 LLM_API_KEY，请在 .env 中设置")

    try:
        from openai import OpenAI
    except ImportError as ex:
        raise LlmClientError("未安装 openai 包，请执行：uv pip install openai") from ex

    client = OpenAI(api_key=config.api_key, base_url=config.api_base)
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


def complete_with_tools(
    config: LlmConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], str],
    *,
    max_rounds: int = 5,
) -> tuple[str, list[dict[str, Any]]]:
    """带工具调用的多轮对话，返回最终回复与更新后的 messages。"""
    if not config.configured:
        raise LlmClientError("未配置 LLM_API_KEY，请在 .env 中设置")

    try:
        from openai import OpenAI
    except ImportError as ex:
        raise LlmClientError("未安装 openai 包，请执行：uv pip install openai") from ex

    client = OpenAI(api_key=config.api_key, base_url=config.api_base)
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
            "tool_calls": [
                {
                    "id": call.id,
                    "type": call.type,
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in tool_calls
            ],
        }
        working.append(assistant_msg)

        for call in tool_calls:
            fn = call.function
            try:
                arguments = json.loads(fn.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            result = tool_executor(fn.name, arguments)
            working.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                }
            )

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
