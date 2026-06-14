"""从 MainEngine 读取 LLM 会话（可选依赖 vnpy-llm）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnpy.trader.engine import MainEngine


def get_last_assistant_message(main_engine: MainEngine | None) -> str:
    """返回当前 LLM 会话中最后一条非空 assistant 消息。"""
    if main_engine is None:
        return ""
    try:
        from vnpy_llm.app.engine import APP_NAME, LlmEngine
    except ImportError:
        return ""
    engine = main_engine.get_engine(APP_NAME)
    if not isinstance(engine, LlmEngine):
        return ""
    for message in reversed(engine.get_messages()):
        if message.role == "assistant" and message.content.strip():
            return message.content.strip()
    return ""
