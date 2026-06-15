"""LangChain ChatOpenAI 工厂。"""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from vnpy_llm.chat.client import LlmClientError
from vnpy_llm.config.settings import LlmConfig


def create_chat_model(config: LlmConfig) -> ChatOpenAI:
    """由 LlmConfig 创建流式 ChatOpenAI（与 chat/client 共用 .env 配置）。"""
    if not config.configured:
        raise LlmClientError("未配置 LLM_API_KEY，请在 .env 中设置")
    return ChatOpenAI(
        model=config.model,
        api_key=SecretStr(config.api_key),
        base_url=config.api_base,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        streaming=True,
    )
