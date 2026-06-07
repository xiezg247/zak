"""大模型配置（OpenAI 兼容 API）。"""

from __future__ import annotations

import os
from dataclasses import dataclass

from pathlib import Path

from dotenv import load_dotenv

DEFAULT_MODEL = "deepseek-chat"
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"


@dataclass(frozen=True)
class LlmConfig:
    api_base: str
    api_key: str
    model: str
    max_tokens: int
    temperature: float

    @property
    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def masked_key(self) -> str:
        key = self.api_key.strip()
        if len(key) <= 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"


def load_llm_config() -> LlmConfig:
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()
    return LlmConfig(
        api_base=os.getenv("LLM_API_BASE", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
        api_key=os.getenv("LLM_API_KEY", "").strip(),
        model=os.getenv("LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
    )
