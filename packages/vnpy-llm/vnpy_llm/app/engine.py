"""大模型引擎：VeighNa 插件壳 + Qt 信号桥接 AgentGateway。"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator

from vnpy.event import EventEngine
from vnpy.trader.engine import BaseEngine, MainEngine
from vnpy.trader.ui import QtCore

from vnpy_common.ai.access import warn_missing_ai_bridges
from vnpy_llm.chat.session_surface import SessionSurfaceStore, Surface
from vnpy_llm.chat.store import ChatMessage, ChatSession, ChatStore
from vnpy_llm.config.settings import LlmConfig
from vnpy_llm.gateway.agent_gateway import AgentGateway
from vnpy_llm.gateway.tool_registry import ToolRegistry
from vnpy_llm.gateway.trace_coordinator import TraceCoordinator
from vnpy_llm.gateway.types import AgentEvent, AgentEventType, SendRequest
from vnpy_llm.tools.status import ToolsStatusSnapshot
from vnpy_llm.trace.trace import TraceStep, TurnTrace
from vnpy_mcp.app.engine import McpEngine
from vnpy_skills.app.engine import SkillEngine

APP_NAME = "Llm"

_logger = logging.getLogger(__name__)


class LlmSignals(QtCore.QObject):
    """LlmEngine → UI 的 Qt 信号集合（流式输出、上下文、工具、Trace）。"""

    messages_changed = QtCore.Signal()
    sessions_changed = QtCore.Signal()
    stream_started = QtCore.Signal()
    stream_delta = QtCore.Signal(str)
    stream_finished = QtCore.Signal()
    stream_cancelled = QtCore.Signal()
    stream_failed = QtCore.Signal(str)
    context_changed = QtCore.Signal(str)
    tools_status_changed = QtCore.Signal(object)
    tool_call_started = QtCore.Signal(str)
    tool_call_finished = QtCore.Signal(str)
    trace_changed = QtCore.Signal()


class LlmEngine(BaseEngine):
    """对话会话 + 上下文 + 流式输出（委托 AgentGateway）。"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__(main_engine, event_engine, APP_NAME)
        self.signals = LlmSignals()
        self._gateway = AgentGateway(main_engine)
        self._gateway.subscribe(self._on_gateway_event)
        warn_missing_ai_bridges(_logger)
        self.register_event()

    @property
    def config(self) -> LlmConfig:
        return self._gateway.config

    @config.setter
    def config(self, value: LlmConfig) -> None:
        self._gateway.config = value

    @property
    def _streaming(self) -> bool:
        return self._gateway._streaming

    @_streaming.setter
    def _streaming(self, value: bool) -> None:
        self._gateway._streaming = value

    @property
    def _cancel_requested(self) -> bool:
        return self._gateway._cancel_requested

    @property
    def store(self) -> ChatStore:
        return self._gateway.store

    @property
    def session_id(self) -> str:
        return self._gateway.session_id

    @session_id.setter
    def session_id(self, value: str) -> None:
        self._gateway.session_id = value

    @property
    def _surface_store(self) -> SessionSurfaceStore:
        return self._gateway.surface_store

    @property
    def _sessions(self) -> object:
        return self._gateway.sessions

    @property
    def _trace(self) -> TraceCoordinator:
        return self._gateway.trace

    @property
    def _tool_registry(self) -> ToolRegistry:
        return self._gateway.tool_registry

    @property
    def skill_engine(self) -> SkillEngine:
        return self._gateway.skill_engine

    @property
    def mcp_engine(self) -> McpEngine:
        return self._gateway.mcp_engine

    def _on_gateway_event(self, event: AgentEvent) -> None:
        if event.type == AgentEventType.CHAT_STARTED:
            self.signals.stream_started.emit()
        elif event.type == AgentEventType.CHAT_DELTA:
            self.signals.stream_delta.emit(event.payload.get("delta", ""))
        elif event.type == AgentEventType.CHAT_FINISHED:
            self.signals.stream_finished.emit()
        elif event.type == AgentEventType.CHAT_CANCELLED:
            self.signals.stream_cancelled.emit()
        elif event.type == AgentEventType.CHAT_FAILED:
            self.signals.stream_failed.emit(event.payload.get("error", ""))
        elif event.type == AgentEventType.CONTEXT_CHANGED:
            self.signals.context_changed.emit(event.payload.get("text", ""))
        elif event.type == AgentEventType.TOOLS_STATUS:
            self.signals.tools_status_changed.emit(event.payload.get("snapshot"))
        elif event.type == AgentEventType.TOOL_STARTED:
            self.signals.tool_call_started.emit(event.payload.get("name", ""))
        elif event.type == AgentEventType.TOOL_FINISHED:
            self.signals.tool_call_finished.emit(event.payload.get("name", ""))
        elif event.type == AgentEventType.TRACE_CHANGED:
            self.signals.trace_changed.emit()
        elif event.type == AgentEventType.SESSION_CHANGED:
            if event.payload.get("messages_changed"):
                self.signals.messages_changed.emit()
            if event.payload.get("sessions_changed"):
                self.signals.sessions_changed.emit()
            if event.payload.get("trace_changed"):
                self.signals.trace_changed.emit()

    def register_event(self) -> None:
        pass  # EVENT_AI_CONTEXT 已移除，改用 context_store 桥接

    def set_extra_context_provider(self, provider: Callable[[], str] | None) -> None:
        self._gateway.set_extra_context_provider(provider)

    def get_context_text(self) -> str:
        return self._gateway.get_context_text()

    def get_messages(self) -> list[ChatMessage]:
        return self._gateway.get_messages()

    def list_sessions(self) -> list[ChatSession]:
        return self._gateway.list_sessions()

    def get_current_session(self) -> ChatSession | None:
        return self._gateway.get_current_session()

    @property
    def active_surface(self) -> Surface:
        return self._gateway.active_surface

    def switch_surface(self, surface: Surface) -> None:
        self._gateway.switch_surface(surface)

    def open_session_for_ask(
        self,
        *,
        surface: Surface,
        new_session: bool = False,
        session_policy: str = "resume",
        scene: str = "",
    ) -> str:
        return self._gateway.open_session_for_ask(
            surface=surface,
            new_session=new_session,
            session_policy=session_policy,
            scene=scene,
        )

    def switch_session(self, session_id: str) -> None:
        self._gateway.switch_session(session_id)

    def rename_session(self, session_id: str, title: str) -> None:
        self._gateway.rename_session(session_id, title)

    def delete_session(self, session_id: str) -> None:
        self._gateway.delete_session(session_id)

    def clear_session(self) -> None:
        self._gateway.clear_session()

    def new_session(
        self,
        *,
        title: str = "新会话",
        surface: Surface | None = None,
        scene: str = "",
    ) -> str:
        return self._gateway.new_session(title=title, surface=surface, scene=scene)

    def build_conversation_messages(self) -> list[dict[str, str]]:
        return self._gateway.build_conversation_messages()

    def build_api_messages(
        self,
        *,
        extra_system: str = "",
    ) -> list[dict[str, str]]:
        return self._gateway.build_api_messages(extra_system=extra_system)

    def reload_skills(self) -> list[str]:
        return self._gateway.reload_skills()

    def reload_mcp(self) -> list[str]:
        return self._gateway.reload_mcp()

    def reload_tools(self) -> tuple[list[str], list[str]]:
        return self._gateway.reload_tools()

    def get_tools_status(self) -> ToolsStatusSnapshot:
        return self._gateway.get_tools_status()

    def _emit_tools_status(self) -> None:
        self._gateway._emit_tools_status()

    def get_enabled_skills(self) -> list[str]:
        return self._gateway.get_enabled_skills()

    def get_enabled_mcp(self) -> list[str]:
        return self._gateway.get_enabled_mcp()

    def is_busy(self) -> bool:
        return self._gateway.is_busy()

    def get_current_session_title(self) -> str:
        return self._gateway.get_current_session_title()

    def request_cancel_stream(self) -> None:
        self._gateway.cancel()

    def get_trace_turns(self) -> list[TurnTrace]:
        return self._gateway.get_trace_turns()

    def get_current_trace_turn(self) -> TurnTrace | None:
        return self._gateway.get_current_trace_turn()

    def get_trace_step(self, step_id: str) -> TraceStep | None:
        return self._gateway.get_trace_step(step_id)

    def format_trace_step_detail(self, step: TraceStep) -> str:
        return self._gateway.format_trace_step_detail(step)

    def append_local_message(self, *, role: str, content: str) -> None:
        self._gateway.append_local_message(self.session_id, role=role, content=content)

    def stream_reply(self, user_text: str) -> Iterator[str]:
        return self._gateway.send(
            SendRequest(session_id=self.session_id, user_text=user_text),
        )

    def reload_config(self) -> LlmConfig:
        return self._gateway.reload_config()

    def close(self) -> None:
        self._gateway.close()
        super().close()
