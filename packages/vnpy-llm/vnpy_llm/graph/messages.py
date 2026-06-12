"""OpenAI 消息 dict ↔ LangChain BaseMessage 转换。"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage


def dict_messages_to_langchain(messages: list[dict[str, Any]]) -> list[BaseMessage]:
    """将 engine/runner 的 role dict 列表转为 LangChain BaseMessage（含历史 tool_calls）。"""
    result: list[BaseMessage] = []
    for item in messages:
        role = item.get("role", "")
        content = item.get("content", "") or ""
        if role == "system":
            result.append(SystemMessage(content=content))
        elif role == "user":
            result.append(HumanMessage(content=content))
        elif role == "assistant":
            tool_calls = item.get("tool_calls")
            if tool_calls:
                result.append(AIMessage(content=content, tool_calls=tool_calls))
            else:
                result.append(AIMessage(content=content))
        elif role == "tool":
            tool_call_id = item.get("tool_call_id", "")
            result.append(ToolMessage(content=content, tool_call_id=tool_call_id))
    return result
