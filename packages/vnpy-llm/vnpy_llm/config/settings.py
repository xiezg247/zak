"""大模型配置（OpenAI 兼容 API）。"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field

from vnpy_common.domain.base import FrozenModel

DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"


class LlmConfig(FrozenModel):
    api_base: str = DEFAULT_BASE_URL
    api_key: str = ""
    model: str = DEFAULT_MODEL
    max_tokens: int = Field(default=4096, ge=256, le=128_000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    @property
    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def masked_key(self) -> str:
        key = self.api_key.strip()
        if len(key) <= 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"


def team_deep_mode_enabled() -> bool:
    """为 True 时团队分析走 3 子 Agent 并行 LLM；默认 False（快速团队：预取 + chief）。"""
    try:
        from vnpy_llm.config.team_prefs import load_team_deep_mode_pref

        return load_team_deep_mode_pref()
    except Exception:
        return os.getenv("LLM_TEAM_DEEP_MODE", "").strip().lower() in ("1", "true", "yes")


def load_llm_config() -> LlmConfig:
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()
    return LlmConfig.model_validate(
        {
            "api_base": os.getenv("LLM_API_BASE", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
            "api_key": os.getenv("LLM_API_KEY", "").strip(),
            "model": os.getenv("LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            "max_tokens": os.getenv("LLM_MAX_TOKENS", "4096"),
            "temperature": os.getenv("LLM_TEMPERATURE", "0.7"),
        }
    )
