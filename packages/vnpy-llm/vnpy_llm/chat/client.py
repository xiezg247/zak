"""OpenAI 兼容流式客户端。"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from vnpy_llm.config.settings import LlmConfig


class LlmClientError(Exception):
    """OpenAI 兼容 API 调用失败。"""


class StreamCancelled(LlmClientError):
    """用户主动中断流式生成。"""


def create_openai_client(config: LlmConfig) -> Any:
    """创建 OpenAI 兼容客户端；未配置 API Key 或未安装 openai 包时抛 LlmClientError。"""
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
    *,
    should_cancel: Callable[[], bool] | None = None,
) -> Iterator[str]:
    """纯文本流式补全；``should_cancel`` 返回 True 时抛 StreamCancelled。"""
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
        if should_cancel and should_cancel():
            raise StreamCancelled("用户已停止生成")
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
