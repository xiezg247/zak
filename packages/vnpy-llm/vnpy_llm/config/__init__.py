"""LLM 配置（OpenAI 兼容 API）。"""

from vnpy_llm.config.settings import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    LlmConfig,
    load_llm_config,
)

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "LlmConfig",
    "load_llm_config",
]
