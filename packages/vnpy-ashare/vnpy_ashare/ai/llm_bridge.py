"""从 MainEngine 读取 LLM 会话（可选依赖 vnpy-llm）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

try:
    from vnpy_llm.app.engine import APP_NAME, LlmEngine
except ImportError:
    APP_NAME = ""
    LlmEngine = None

if TYPE_CHECKING:
    from vnpy.trader.engine import MainEngine

    from vnpy_llm.app.engine import LlmEngine


def get_last_assistant_message(main_engine: MainEngine | None) -> str:
    """返回当前 LLM 会话中最后一条非空 assistant 消息。"""
    if main_engine is None or LlmEngine is None:
        return ""
    engine = main_engine.get_engine(APP_NAME)
    if not isinstance(engine, LlmEngine):
        return ""
    for message in reversed(engine.get_messages()):
        if message.role == "assistant" and message.content.strip():
            return cast(str, message.content.strip())
    return ""


def get_llm_engine(main_engine: MainEngine | None) -> LlmEngine | None:
    """从 MainEngine 获取 LlmEngine（可选依赖 vnpy-llm）。"""
    if main_engine is None or LlmEngine is None:
        return None
    engine = main_engine.get_engine(APP_NAME)
    if isinstance(engine, LlmEngine):
        return engine
    return None
