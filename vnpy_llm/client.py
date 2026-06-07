"""OpenAI 兼容流式客户端。"""

from __future__ import annotations

from collections.abc import Iterator
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
