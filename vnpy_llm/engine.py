"""大模型引擎。"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from vnpy.event import Event, EventEngine
from vnpy.trader.engine import BaseEngine, MainEngine
from vnpy.trader.ui import QtCore

from vnpy_llm.client import LlmClientError, stream_chat_completion
from vnpy_llm.config import LlmConfig, load_llm_config
from vnpy_llm.events import EVENT_AI_CONTEXT, AiContextData
from vnpy_llm.prompts import SYSTEM_PROMPT
from vnpy_llm.store import ChatMessage, ChatStore

APP_NAME = "Llm"


class LlmSignals(QtCore.QObject):
    messages_changed = QtCore.Signal()
    stream_started = QtCore.Signal()
    stream_delta = QtCore.Signal(str)
    stream_finished = QtCore.Signal()
    stream_failed = QtCore.Signal(str)
    context_changed = QtCore.Signal(str)


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
        self.register_event()

    def register_event(self) -> None:
        self.event_engine.register(EVENT_AI_CONTEXT, self._on_context_event)

    def set_extra_context_provider(self, provider: Callable[[], str] | None) -> None:
        self._extra_context_provider = provider

    def _on_context_event(self, event: Event) -> None:
        data = event.data
        if not isinstance(data, AiContextData):
            return
        self._context = data
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
        context_text = self.get_context_text()
        if context_text:
            system_parts.append("\n【当前终端上下文】\n" + context_text)
        messages: list[dict[str, str]] = [{"role": "system", "content": "\n".join(system_parts)}]
        for item in self.get_messages():
            messages.append({"role": item.role, "content": item.content})
        return messages

    def append_local_message(self, *, role: str, content: str) -> None:
        self.store.append_message(self.session_id, role=role, content=content)
        self.signals.messages_changed.emit()

    def stream_reply(self, user_text: str) -> Iterator[str]:
        if self._streaming:
            raise LlmClientError("上一条回复仍在生成中")
        self._streaming = True
        self.signals.stream_started.emit()
        self.append_local_message(role="user", content=user_text)

        chunks: list[str] = []
        try:
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
