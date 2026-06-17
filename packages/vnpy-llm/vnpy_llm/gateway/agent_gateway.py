"""AI Agent 控制面：会话、上下文、工具、流式回复与事件订阅。"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any, cast

from vnpy.trader.engine import MainEngine

from vnpy_common.ai.access import get_ai_context, register_context_listener
from vnpy_common.ai.protocol import AiContextData
from vnpy_llm.chat.client import LlmClientError, StreamCancelled
from vnpy_llm.chat.session_surface import SessionSurfaceStore, Surface
from vnpy_llm.chat.store import ChatMessage, ChatSession, ChatStore
from vnpy_llm.config.settings import LlmConfig, load_llm_config
from vnpy_llm.gateway.agent_runtime import AgentRuntime
from vnpy_llm.gateway.context_assembler import ContextAssembler
from vnpy_llm.gateway.routing_plane import RoutingPlane
from vnpy_llm.gateway.session_manager import SessionManager, SessionNotification
from vnpy_llm.gateway.tool_registry import ToolRegistry
from vnpy_llm.gateway.trace_coordinator import TraceCoordinator
from vnpy_llm.gateway.types import AgentEvent, AgentEventType, SendRequest
from vnpy_llm.graph.state import GraphStreamContext
from vnpy_llm.routing.router import RouteContext, normalize_team_command
from vnpy_llm.tools.audit import log_tool_call
from vnpy_llm.tools.status import ToolsStatusSnapshot
from vnpy_llm.trace.trace import TraceStep, TurnTrace
from vnpy_mcp import McpEngine
from vnpy_skills import SkillEngine

EventListener = Callable[[AgentEvent], None]


class AgentGateway:
    """AI 控制面：统一 send / cancel / subscribe 与会话管理。"""

    def __init__(self, main_engine: MainEngine) -> None:
        self.config: LlmConfig = load_llm_config()
        self._streaming = False
        self._cancel_requested = False
        self._listeners: list[EventListener] = []
        self._sessions = SessionManager(on_notify=self._on_session_notify)
        self._trace = TraceCoordinator(on_changed=self._on_trace_changed)
        self._trace.ensure_session_loaded(self._sessions.session_id)
        self._tool_registry = ToolRegistry(main_engine)
        self._context = ContextAssembler(self._tool_registry)
        self._routing = RoutingPlane()
        self._team_run_cache: dict[str, Any] = {}
        register_context_listener(self._on_context_changed)
        self._emit_tools_status()

    @property
    def sessions(self) -> SessionManager:
        return self._sessions

    @property
    def store(self) -> ChatStore:
        return self._sessions.store

    @property
    def session_id(self) -> str:
        return self._sessions.session_id

    @session_id.setter
    def session_id(self, value: str) -> None:
        self._sessions.session_id = value

    @property
    def surface_store(self) -> SessionSurfaceStore:
        return self._sessions.surface_store

    @property
    def tool_registry(self) -> ToolRegistry:
        return self._tool_registry

    @property
    def skill_engine(self) -> SkillEngine:
        return self._tool_registry.skill_engine

    @property
    def mcp_engine(self) -> McpEngine:
        return self._tool_registry.mcp_engine

    @property
    def trace(self) -> TraceCoordinator:
        return self._trace

    def subscribe(self, listener: EventListener) -> Callable[[], None]:
        """订阅控制面事件；返回 unsubscribe 函数。"""
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def _emit(self, event: AgentEvent) -> None:
        for listener in self._listeners:
            listener(event)

    def _on_session_notify(self, note: SessionNotification) -> None:
        if note.trace_session_loaded:
            self._trace.ensure_session_loaded(note.trace_session_loaded)
        if note.trace_clear_session:
            self._trace.clear_session(note.trace_clear_session)
        payload: dict[str, Any] = {}
        if note.messages_changed:
            payload["messages_changed"] = True
        if note.sessions_changed:
            payload["sessions_changed"] = True
        if note.trace_changed:
            payload["trace_changed"] = True
        if payload:
            self._emit(AgentEvent(AgentEventType.SESSION_CHANGED, payload))

    def _on_trace_changed(self) -> None:
        self._emit(AgentEvent(AgentEventType.TRACE_CHANGED, {}))

    def _on_context_changed(self, data: AiContextData) -> None:
        self._emit(
            AgentEvent(
                AgentEventType.CONTEXT_CHANGED,
                {"text": data.to_text()},
            )
        )

    def set_extra_context_provider(self, provider: Callable[[], str] | None) -> None:
        self._context.set_extra_context_provider(provider)

    def get_context_text(self) -> str:
        return self._context.get_context_text()

    def get_messages(self, session_id: str | None = None) -> list[ChatMessage]:
        return self._sessions.get_messages(session_id)

    def list_sessions(self) -> list[ChatSession]:
        return self._sessions.list_sessions()

    def get_current_session(self) -> ChatSession | None:
        return self._sessions.get_session()

    @property
    def active_surface(self) -> Surface:
        return self._sessions.active_surface

    def switch_surface(self, surface: Surface) -> None:
        self._sessions.switch_surface(surface)

    def open_session_for_ask(
        self,
        *,
        surface: Surface,
        new_session: bool = False,
        session_policy: str = "resume",
        scene: str = "",
    ) -> str:
        return self._sessions.open_session_for_ask(
            surface=surface,
            new_session=new_session,
            session_policy=session_policy,
            scene=scene,
        )

    def switch_session(self, session_id: str) -> None:
        self._sessions.switch_session(session_id)

    def rename_session(self, session_id: str, title: str) -> None:
        self._sessions.rename_session(session_id, title)

    def delete_session(self, session_id: str) -> None:
        self._sessions.delete_session(session_id)

    def clear_session(self) -> None:
        self._sessions.clear_session()

    def new_session(
        self,
        *,
        title: str = "新会话",
        surface: Surface | None = None,
        scene: str = "",
    ) -> str:
        return self._sessions.new_session(title=title, surface=surface, scene=scene)

    def build_conversation_messages(self, session_id: str | None = None) -> list[dict[str, str]]:
        messages = self.get_messages(session_id)
        return self._context.build_conversation_messages(messages)

    def build_api_messages(
        self,
        session_id: str | None = None,
        *,
        extra_system: str = "",
    ) -> list[dict[str, str]]:
        messages = self.get_messages(session_id)
        return self._context.build_api_messages(messages, extra_system=extra_system)

    def reload_skills(self) -> list[str]:
        return self._tool_registry.reload_skills()

    def reload_mcp(self) -> list[str]:
        return self._tool_registry.reload_mcp()

    def reload_tools(self) -> tuple[list[str], list[str]]:
        skills, mcp = self._tool_registry.reload_all()
        self._emit_tools_status()
        return skills, mcp

    def get_tools_status(self) -> ToolsStatusSnapshot:
        return self._tool_registry.get_tools_status()

    def _emit_tools_status(self) -> None:
        self._emit(
            AgentEvent(
                AgentEventType.TOOLS_STATUS,
                {"snapshot": self.get_tools_status()},
            )
        )

    def get_enabled_skills(self) -> list[str]:
        return self._tool_registry.get_enabled_skills()

    def get_enabled_mcp(self) -> list[str]:
        return self._tool_registry.get_enabled_mcp()

    def is_busy(self) -> bool:
        return self._streaming

    def get_current_session_title(self) -> str:
        return self._sessions.get_current_session_title()

    def cancel(self, session_id: str | None = None) -> None:
        """请求中断当前流式回复（session_id 预留多会话并发）。"""
        if session_id is not None and session_id != self.session_id:
            return
        self._cancel_requested = True

    def get_trace_turns(self, session_id: str | None = None) -> list[TurnTrace]:
        return self._trace.list_turns(session_id or self.session_id)

    def get_current_trace_turn(self, session_id: str | None = None) -> TurnTrace | None:
        return self._trace.current_turn_for_session(session_id or self.session_id)

    def get_trace_step(self, step_id: str) -> TraceStep | None:
        return self._trace.get_step(step_id)

    def format_trace_step_detail(self, step: TraceStep) -> str:
        return self._trace.format_step_detail(step)

    def append_local_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
    ) -> None:
        self._sessions.append_message(session_id, role=role, content=content)

    def _finalize_team_report(self, graph_ctx: GraphStreamContext | None, content: str) -> str:
        """团队分析完成后静默保存研报，并在正文末尾追加可点击链接。"""
        if graph_ctx is None or graph_ctx.analysis.route.category != "team_analysis":
            return content
        if "综合研判" not in content:
            return content
        try:
            from vnpy_ashare.services.analysis_detail.team_report import (
                persist_team_analysis_report,
                team_report_href,
            )
            from vnpy_llm.graph.team_symbol import resolve_team_symbol

            ctx = get_ai_context()
            cache = getattr(self, "_team_run_cache", None) or {}
            prefetch = cache.get("team_prefetch") or graph_ctx.team_prefetch or {}
            team_scores = cache.get("team_scores") or graph_ctx.team_scores
            symbol = resolve_team_symbol(
                user_text=graph_ctx.user_text,
                context_symbol=ctx.symbol,
                context_exchange=ctx.exchange,
            ) or prefetch.get("symbol")
            if not symbol:
                return content
            row = persist_team_analysis_report(
                str(symbol),
                content,
                name=str(ctx.name or prefetch.get("name") or ""),
                team_scores=team_scores,
            )
            if row:
                report_id = int(row.get("id", 0))
                vt = str(prefetch.get("symbol") or symbol)
                href = team_report_href(report_id, vt)
                return f"{content}\n\n📁 [打开投研研报 #{report_id}]({href})"
        except Exception:
            pass
        return content

    def _team_prefetch_provider(self, symbol: str) -> dict[str, Any]:
        engine = getattr(self._tool_registry._main_engine, "engines", {}).get("Ashare")
        if engine is None or not hasattr(engine, "analysis_service"):
            return {"symbol": symbol, "error": "分析服务未就绪"}
        return cast(dict[str, Any], engine.analysis_service.prefetch_team_facts(symbol))

    def _build_team_trace_handler(self) -> Callable[[str, str, dict[str, Any]], None]:
        from typing import cast

        from vnpy_llm.graph.state import AGENT_STREAM_LABELS, AgentName

        team_steps: dict[str, str] = {}

        def handler(phase: str, agent: str, detail: dict[str, Any]) -> None:
            if phase == "prefetch_start":
                team_steps["prefetch"] = self._trace.begin_team_step("team:prefetch", "预取团队数据…")
            elif phase == "prefetch_done":
                step_id = team_steps.get("prefetch")
                weighted = detail.get("weighted", "-")
                if step_id:
                    self._trace.finish_team_step(
                        step_id,
                        summary=f"预取完成 · 加权 {weighted}",
                        detail=detail,
                    )
                self._team_run_cache = {
                    "team_scores": detail.get("team_scores"),
                    "team_prefetch": detail.get("team_prefetch"),
                }
            elif phase == "prefetch_error":
                step_id = team_steps.pop("prefetch", None)
                if step_id:
                    self._trace.finish_team_step(
                        step_id,
                        summary="预取失败",
                        ok=False,
                        detail=detail,
                    )
            elif phase == "agent_start":
                agent_name = cast(AgentName, agent)
                label = AGENT_STREAM_LABELS.get(agent_name, agent)
                team_steps[agent] = self._trace.begin_team_step(f"team:{agent}", f"{label}生成中…")
            elif phase == "agent_done":
                step_id = team_steps.pop(agent, None)
                if not step_id:
                    return
                agent_name = cast(AgentName, agent)
                label = AGENT_STREAM_LABELS.get(agent_name, agent)
                if detail.get("ok", True):
                    score = detail.get("score")
                    summary = f"{label}完成" + (f" · {score}分" if score is not None else "")
                    self._trace.finish_team_step(step_id, summary=summary, detail=detail)
                else:
                    self._trace.finish_team_step(
                        step_id,
                        summary=f"{label}异常",
                        ok=False,
                        detail=detail,
                    )

        return handler

    def _execute_tool(self, session_id: str, name: str, arguments: dict[str, Any]) -> str:
        step_id = self._trace.begin_tool(name, arguments)
        self._emit(AgentEvent(AgentEventType.TOOL_STARTED, {"name": name}))
        result = ""
        success = True
        try:
            result, success = self._tool_registry.execute(name, arguments)
            return result
        except Exception as ex:
            success = False
            result = json.dumps({"error": str(ex)}, ensure_ascii=False)
            return result
        finally:
            self._trace.finish_tool(step_id, result=result, success=success)
            try:
                if result:
                    log_tool_call(
                        session_id=session_id,
                        tool_name=name,
                        arguments=arguments,
                        result=result,
                        success=success,
                    )
            except Exception:
                pass
            self._emit(AgentEvent(AgentEventType.TOOL_FINISHED, {"name": name}))

    def send(self, request: SendRequest) -> Iterator[str]:
        """单轮回复入口：有 Skill 工具走 LangGraph，否则纯文本流。"""
        if self._streaming:
            raise LlmClientError("上一条回复仍在生成中")

        session_id = request.session_id
        user_text = request.user_text
        expanded = normalize_team_command(user_text)
        effective_text = expanded if expanded else user_text
        if request.surface is not None:
            self.switch_surface(request.surface)

        self._streaming = True
        self._cancel_requested = False
        self._team_run_cache.clear()
        self._emit(AgentEvent(AgentEventType.CHAT_STARTED, {"session_id": session_id}))
        self.append_local_message(session_id, role="user", content=user_text)
        turn = self._trace.begin_turn(session_id, user_text)
        turn_ok = True
        cancelled = False

        def should_cancel() -> bool:
            return self._cancel_requested

        chunks: list[str] = []

        def _persist_partial() -> None:
            content = "".join(chunks).strip()
            if content:
                self.append_local_message(session_id, role="assistant", content=content)

        def _execute_tool_bound(name: str, arguments: dict[str, Any]) -> str:
            return self._execute_tool(session_id, name, arguments)

        try:
            all_tools = self._tool_registry.get_openai_tools()
            mcp_names = self._tool_registry.get_mcp_tool_names()
            route_ctx: RouteContext | None = None
            graph_ctx: GraphStreamContext | None = None
            if all_tools:
                routing = self._routing.route(
                    self.config,
                    effective_text,
                    all_tools,
                    page=get_ai_context().page,
                    mcp_tool_names=mcp_names,
                )
                route_ctx = routing.route_ctx
                self._trace.add_routing(
                    route_ctx,
                    user_text=effective_text,
                    supervisor=routing.supervisor,
                )
                graph_ctx = self._context.build_graph_stream_context(route_ctx, effective_text)
            conversation_messages = self.build_conversation_messages(session_id)
            api_messages = self.build_api_messages(session_id)
            chunks = []
            self._trace.begin_reply()
            team_trace = self._build_team_trace_handler() if (graph_ctx is not None and graph_ctx.analysis.route.category == "team_analysis") else None
            prefetch_provider = self._team_prefetch_provider if graph_ctx is not None and graph_ctx.analysis.route.category == "team_analysis" else None
            for delta in AgentRuntime.stream_deltas(
                self.config,
                all_tools=all_tools,
                conversation_messages=conversation_messages,
                api_messages=api_messages,
                route_ctx=route_ctx,
                graph_ctx=graph_ctx,
                mcp_tool_names=mcp_names,
                tool_executor=_execute_tool_bound,
                should_cancel=should_cancel,
                on_handoff=self._trace.on_handoff,
                prefetch_provider=prefetch_provider,
                on_team_trace=team_trace,
            ):
                chunks.append(delta)
                self._emit(AgentEvent(AgentEventType.CHAT_DELTA, {"delta": delta}))
                yield delta
            content = "".join(chunks).strip()
            if content:
                content = self._finalize_team_report(graph_ctx, content)
                if content != "".join(chunks).strip():
                    suffix = content[len("".join(chunks).strip()) :]
                    if suffix:
                        self._emit(AgentEvent(AgentEventType.CHAT_DELTA, {"delta": suffix}))
                        yield suffix
            if content:
                self.append_local_message(session_id, role="assistant", content=content)
            self._trace.finish_reply()
        except StreamCancelled:
            cancelled = True
            turn_ok = False
            _persist_partial()
            self._emit(AgentEvent(AgentEventType.CHAT_CANCELLED, {"session_id": session_id}))
        except Exception as ex:
            turn_ok = False
            self._trace.add_error(str(ex))
            self._emit(
                AgentEvent(
                    AgentEventType.CHAT_FAILED,
                    {"session_id": session_id, "error": str(ex)},
                )
            )
            raise
        finally:
            self._streaming = False
            self._cancel_requested = False
            if not cancelled:
                self._trace.finish_turn(ok=turn_ok)
            self._emit(
                AgentEvent(
                    AgentEventType.CHAT_FINISHED,
                    {"session_id": session_id, "turn_id": turn.turn_id},
                )
            )

    def stream_reply(self, user_text: str) -> Iterator[str]:
        """使用当前 session 的便捷入口（与 LlmEngine.stream_reply 兼容）。"""
        return self.send(
            SendRequest(session_id=self.session_id, user_text=user_text),
        )

    def reload_config(self) -> LlmConfig:
        from dotenv import load_dotenv

        from vnpy_common.paths import ENV_FILE

        if ENV_FILE.is_file():
            load_dotenv(ENV_FILE, override=True)
        self.config = load_llm_config()
        return self.config

    def close(self) -> None:
        self._sessions.bind_active_surface_on_close()
