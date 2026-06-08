"""大模型引擎。"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from vnpy.event import Event, EventEngine
from vnpy.trader.engine import BaseEngine, MainEngine
from vnpy.trader.ui import QtCore

from vnpy_llm.client import LlmClientError, complete_with_tools, stream_chat_completion
from vnpy_llm.config import LlmConfig, load_llm_config
from vnpy_llm.events import EVENT_AI_CONTEXT, AiContextData
from vnpy_llm.prompts import SYSTEM_PROMPT
from vnpy_llm.store import ChatMessage, ChatStore
from vnpy_llm.tools_status import ToolsStatusSnapshot, build_tools_status
from vnpy_mcp import McpEngine
from vnpy_skills import SkillEngine

from vnpy_ashare.ai.session_context import set_ai_context

APP_NAME = "Llm"


class LlmSignals(QtCore.QObject):
    messages_changed = QtCore.Signal()
    stream_started = QtCore.Signal()
    stream_delta = QtCore.Signal(str)
    stream_finished = QtCore.Signal()
    stream_failed = QtCore.Signal(str)
    context_changed = QtCore.Signal(str)
    tools_status_changed = QtCore.Signal(object)


class LlmEngine(BaseEngine):
    """对话会话 + 上下文 + 流式输出。"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__(main_engine, event_engine, APP_NAME)
        self.signals = LlmSignals()
        self.store = ChatStore()
        self.config: LlmConfig = load_llm_config()
        self.session_id: str = self.store.get_or_create_default_session()
        self._context = AiContextData()
        self._extra_context_provider: Callable[[], str] | None = None
        self._streaming = False
        self.skill_engine = SkillEngine()
        self.skill_engine.load_all()
        self._enabled_skills = self.skill_engine.init_skills()
        self.mcp_engine = McpEngine()
        self.mcp_engine.load_all()
        self._enabled_mcp = self.mcp_engine.init_providers()
        self.register_event()
        self._emit_tools_status()

    def register_event(self) -> None:
        self.event_engine.register(EVENT_AI_CONTEXT, self._on_context_event)

    def set_extra_context_provider(self, provider: Callable[[], str] | None) -> None:
        self._extra_context_provider = provider

    def _on_context_event(self, event: Event) -> None:
        data = event.data
        if not isinstance(data, AiContextData):
            return
        self._context = data
        set_ai_context(data)
        text = self.get_context_text()
        self.signals.context_changed.emit(text)

    def get_context_text(self) -> str:
        parts: list[str] = []
        context_text = self._context.to_text()
        if context_text:
            parts.append(context_text)
        if self._extra_context_provider:
            extra = self._extra_context_provider().strip()
            if extra:
                parts.append(extra)
        return "\n".join(parts)

    def get_messages(self) -> list[ChatMessage]:
        return self.store.list_messages(self.session_id)

    def clear_session(self) -> None:
        self.store.clear_messages(self.session_id)
        self.signals.messages_changed.emit()

    def new_session(self) -> None:
        self.session_id = self.store.create_session()
        self.signals.messages_changed.emit()

    def build_api_messages(self) -> list[dict[str, str]]:
        system_parts = [SYSTEM_PROMPT]
        skills_text = self.skill_engine.build_skills_prompt()
        if skills_text:
            system_parts.append(skills_text)
        mcp_text = self.mcp_engine.build_mcp_prompt()
        if mcp_text:
            system_parts.append(mcp_text)
        context_text = self.get_context_text()
        if context_text:
            system_parts.append("\n【当前终端上下文】\n" + context_text)
        messages: list[dict[str, str]] = [{"role": "system", "content": "\n".join(system_parts)}]
        for item in self.get_messages():
            messages.append({"role": item.role, "content": item.content})
        return messages

    def reload_skills(self) -> list[str]:
        self._enabled_skills = self.skill_engine.reload_skills()
        return self._enabled_skills

    def reload_mcp(self) -> list[str]:
        self._enabled_mcp = self.mcp_engine.reload_providers()
        return self._enabled_mcp

    def reload_tools(self) -> tuple[list[str], list[str]]:
        skills = self.reload_skills()
        mcp = self.reload_mcp()
        self._emit_tools_status()
        return skills, mcp

    def get_tools_status(self) -> ToolsStatusSnapshot:
        return build_tools_status(self.skill_engine, self.mcp_engine)

    def _emit_tools_status(self) -> None:
        self.signals.tools_status_changed.emit(self.get_tools_status())

    def get_enabled_skills(self) -> list[str]:
        return list(self._enabled_skills)

    def get_enabled_mcp(self) -> list[str]:
        return list(self._enabled_mcp)

    def _get_openai_tools(self) -> list[dict[str, Any]]:
        tools = self.skill_engine.get_openai_tools()
        tools.extend(self.mcp_engine.get_openai_tools())
        return tools

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        mcp_names = {spec.name for spec in self.mcp_engine.get_tool_specs()}
        if name in mcp_names:
            return self.mcp_engine.execute_tool(name, arguments)
        return self.skill_engine.execute_tool(name, arguments)

    def append_local_message(self, *, role: str, content: str) -> None:
        self.store.append_message(self.session_id, role=role, content=content)
        self.signals.messages_changed.emit()

    def stream_reply(self, user_text: str) -> Iterator[str]:
        if self._streaming:
            raise LlmClientError("上一条回复仍在生成中")
        self._streaming = True
        self.signals.stream_started.emit()
        self.append_local_message(role="user", content=user_text)

        try:
            tools = self._get_openai_tools()
            if tools:
                messages = self.build_api_messages()
                content, _ = complete_with_tools(
                    self.config,
                    messages,
                    tools,
                    self._execute_tool,
                )
                if content:
                    chunk_size = 24
                    for index in range(0, len(content), chunk_size):
                        delta = content[index : index + chunk_size]
                        self.signals.stream_delta.emit(delta)
                        yield delta
                    self.append_local_message(role="assistant", content=content)
            else:
                chunks: list[str] = []
                for delta in stream_chat_completion(self.config, self.build_api_messages()):
                    chunks.append(delta)
                    self.signals.stream_delta.emit(delta)
                    yield delta
                content = "".join(chunks).strip()
                if content:
                    self.append_local_message(role="assistant", content=content)
        except Exception as ex:
            self.signals.stream_failed.emit(str(ex))
            raise
        finally:
            self._streaming = False
            self.signals.stream_finished.emit()

    def reload_config(self) -> None:
        self.config = load_llm_config()

    def close(self) -> None:
        self.event_engine.unregister(EVENT_AI_CONTEXT, self._on_context_event)
        super().close()
