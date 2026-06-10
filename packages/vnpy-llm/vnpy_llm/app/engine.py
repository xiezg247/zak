"""大模型引擎：会话管理、流式对话、工具调用与 Trace。"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

from vnpy.event import EventEngine
from vnpy.trader.engine import BaseEngine, MainEngine
from vnpy.trader.ui import QtCore

from vnpy_common.ai.access import get_ai_context, register_context_listener
from vnpy_common.ai.protocol import AiContextData
from vnpy_llm.chat.client import LlmClientError, StreamCancelled, stream_chat_completion, stream_with_tools
from vnpy_llm.chat.session_surface import SessionSurfaceStore, Surface
from vnpy_llm.chat.store import MAX_TOOL_RESULT_CHARS, ChatMessage, ChatSession, ChatStore
from vnpy_llm.config.settings import LlmConfig, load_llm_config
from vnpy_llm.routing.prompts import SYSTEM_PROMPT, build_page_prompt, build_strategy_prompt
from vnpy_llm.routing.router import build_route_context
from vnpy_llm.tools.audit import log_tool_call
from vnpy_llm.tools.labels import tool_display_name
from vnpy_llm.tools.result import enrich_tool_result
from vnpy_llm.tools.status import ToolsStatusSnapshot, build_tools_status
from vnpy_llm.trace.persistence import TracePersistence
from vnpy_llm.trace.trace import TraceStep, TraceStore, TurnTrace, preview_text
from vnpy_mcp import McpEngine
from vnpy_skills import SkillEngine

APP_NAME = "Llm"


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
    screener_draft_ready = QtCore.Signal(str)
    recipe_draft_ready = QtCore.Signal(str)
    trace_changed = QtCore.Signal()


class LlmEngine(BaseEngine):
    """对话会话 + 上下文 + 流式输出。"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__(main_engine, event_engine, APP_NAME)
        self.signals = LlmSignals()
        self.store = ChatStore()
        self.config: LlmConfig = load_llm_config()
        self._surface_store = SessionSurfaceStore()
        default_session_id = self.store.get_or_create_default_session()
        floating_id = self._ensure_session_exists(
            self._surface_store.get("floating", fallback=default_session_id),
        )
        assistant_id = self._ensure_session_exists(
            self._surface_store.get("assistant", fallback=default_session_id),
        )
        self._surface_store.set("floating", floating_id)
        self._surface_store.set("assistant", assistant_id)
        self._active_surface: Surface = "assistant"
        self.session_id: str = assistant_id
        self._extra_context_provider: Callable[[], str] | None = None
        self._streaming = False
        self._cancel_requested = False
        self._trace_store = TraceStore(TracePersistence())
        self._trace_store.ensure_session_loaded(self.session_id)
        self._reply_step_id: str | None = None
        ashare_engine = getattr(main_engine, "engines", {}).get("Ashare")
        services: dict[str, object] = {}
        if ashare_engine is not None and hasattr(ashare_engine, "bar_service"):
            services = {
                "bar": ashare_engine.bar_service,
                "quote": ashare_engine.quote_service,
                "backtest": ashare_engine.backtest_service,
                "screening": ashare_engine.screening_service,
                "watchlist": ashare_engine.watchlist_service,
                "analysis": ashare_engine.analysis_service,
                "sentiment": ashare_engine.sentiment_service,
            }
        self.skill_engine = SkillEngine(services=services)
        self.skill_engine.load_all()
        self._enabled_skills = self.skill_engine.init_skills()
        self.mcp_engine = McpEngine()
        self.mcp_engine.load_all()
        self._enabled_mcp = self.mcp_engine.init_providers()
        if ashare_engine is not None and hasattr(ashare_engine, "analysis_service"):
            ashare_engine.analysis_service.bind_mcp(
                self.mcp_engine.execute_tool,
                [spec.name for spec in self.mcp_engine.get_tool_specs()],
            )
        if ashare_engine is not None and hasattr(ashare_engine, "backtest_service"):
            ashare_engine.backtest_service.get_last_summary()
        self.register_event()
        register_context_listener(self._on_session_context_changed)
        self._emit_tools_status()

    def _on_session_context_changed(self, data: AiContextData) -> None:
        self.signals.context_changed.emit(data.to_text())

    def register_event(self) -> None:
        pass  # EVENT_AI_CONTEXT 已移除，改用 context_store 桥接

    def set_extra_context_provider(self, provider: Callable[[], str] | None) -> None:
        self._extra_context_provider = provider

    def get_context_text(self) -> str:
        parts: list[str] = []
        # 从 context_store 读取（QuotesPage 通过 set_ai_context 写入）
        ctx = get_ai_context()
        context_text = ctx.to_text()
        if context_text:
            parts.append(context_text)
        if self._extra_context_provider:
            extra = self._extra_context_provider().strip()
            if extra:
                parts.append(extra)
        return "\n".join(parts)

    def get_messages(self) -> list[ChatMessage]:
        return self.store.list_messages(self.session_id)

    def list_sessions(self) -> list[ChatSession]:
        return self.store.list_sessions()

    def get_current_session(self) -> ChatSession | None:
        return self.store.get_session(self.session_id)

    @property
    def active_surface(self) -> Surface:
        return self._active_surface

    def _ensure_session_exists(self, session_id: str) -> str:
        if self.store.get_session(session_id) is not None:
            return session_id
        return self.store.get_or_create_default_session()

    def _bind_surface_session(self, surface: Surface, session_id: str) -> None:
        session_id = self._ensure_session_exists(session_id)
        self._surface_store.set(surface, session_id)

    def switch_surface(self, surface: Surface) -> None:
        """切换 UI 轨道并恢复该轨道上次会话。"""
        if surface == self._active_surface:
            return
        self._bind_surface_session(self._active_surface, self.session_id)
        self._active_surface = surface
        next_id = self._surface_store.get(surface, fallback=self.session_id)
        next_id = self._ensure_session_exists(next_id)
        self._bind_surface_session(surface, next_id)
        if next_id != self.session_id:
            self.session_id = next_id
            self._trace_store.ensure_session_loaded(next_id)
            self.signals.messages_changed.emit()
            self.signals.sessions_changed.emit()
            self.signals.trace_changed.emit()

    def open_session_for_ask(
        self,
        *,
        surface: Surface,
        new_session: bool = False,
        session_policy: str = "resume",
        scene: str = "",
    ) -> str:
        """打开悬浮/全屏 AI 前的统一会话入口。"""
        self.switch_surface(surface)
        if new_session or session_policy == "new":
            session_id = self.new_session(surface=surface, scene=scene)
        else:
            session_id = self.session_id
            if scene.strip():
                self._apply_session_scene(session_id, scene)
        return session_id

    def _apply_session_scene(self, session_id: str, scene: str) -> None:
        cleaned = scene.strip()
        if not cleaned:
            return
        self.store.update_session_scene(session_id, cleaned)
        self.signals.sessions_changed.emit()

    def switch_session(self, session_id: str) -> None:
        if session_id == self.session_id:
            return
        if self.store.get_session(session_id) is None:
            return
        self.session_id = session_id
        self._bind_surface_session(self._active_surface, session_id)
        self._trace_store.ensure_session_loaded(session_id)
        self.signals.messages_changed.emit()
        self.signals.sessions_changed.emit()
        self.signals.trace_changed.emit()

    def rename_session(self, session_id: str, title: str) -> None:
        self.store.update_session_title(session_id, title)
        self.signals.sessions_changed.emit()

    def delete_session(self, session_id: str) -> None:
        self._trace_store.clear_session(session_id)
        self.store.delete_session(session_id)
        remaining = self.store.list_sessions(limit=1)
        replacement = remaining[0].id if remaining else self.store.create_session()
        self._surface_store.clear_binding(session_id, replacement=replacement)
        if session_id == self.session_id:
            self.session_id = self._ensure_session_exists(
                self._surface_store.get(self._active_surface, fallback=replacement),
            )
            self._bind_surface_session(self._active_surface, self.session_id)
            self._trace_store.ensure_session_loaded(self.session_id)
            self.signals.messages_changed.emit()
            self.signals.trace_changed.emit()
        self.signals.sessions_changed.emit()

    def clear_session(self) -> None:
        self.store.clear_messages(self.session_id)
        self._trace_store.clear_session(self.session_id)
        self.signals.trace_changed.emit()
        self.signals.messages_changed.emit()
        self.signals.sessions_changed.emit()

    def new_session(
        self,
        *,
        title: str = "新会话",
        surface: Surface | None = None,
        scene: str = "",
    ) -> str:
        target = surface or self._active_surface
        session_id = self.store.create_session(title=title, scene=scene.strip())
        self._bind_surface_session(target, session_id)
        if target == self._active_surface:
            self.session_id = session_id
            self._trace_store.ensure_session_loaded(session_id)
            self.signals.messages_changed.emit()
            self.signals.trace_changed.emit()
        self.signals.sessions_changed.emit()
        return session_id

    def _maybe_update_session_title(self, user_text: str) -> None:
        session = self.store.get_session(self.session_id)
        if session is None or session.title not in ("新会话", "默认会话"):
            return
        title = user_text.replace("\n", " ").strip()[:30]
        if not title:
            return
        self.store.update_session_title(self.session_id, title)
        self.signals.sessions_changed.emit()

    def build_api_messages(self, *, extra_system: str = "") -> list[dict[str, str]]:
        system_parts = [SYSTEM_PROMPT]
        tools_summary = self._build_tools_summary()
        if tools_summary:
            system_parts.append(tools_summary)
        skills_text = self.skill_engine.build_skills_prompt()
        if skills_text:
            system_parts.append(skills_text)
        strategy_prompt = build_strategy_prompt()
        if strategy_prompt:
            system_parts.append(strategy_prompt)
        mcp_text = self.mcp_engine.build_mcp_prompt()
        if mcp_text:
            system_parts.append(mcp_text)
        context_text = self.get_context_text()
        if context_text:
            system_parts.append("\n【当前终端上下文】\n" + context_text)
        page_prompt = build_page_prompt(get_ai_context().page)
        if page_prompt:
            system_parts.append(page_prompt)
        if extra_system.strip():
            system_parts.append(extra_system.strip())
        messages: list[dict[str, str]] = [{"role": "system", "content": "\n".join(system_parts)}]
        for item in self.get_messages():
            content = item.content
            if item.role == "tool" and len(content) > MAX_TOOL_RESULT_CHARS:
                content = content[:MAX_TOOL_RESULT_CHARS] + "\n...(结果过长已截断)"
            messages.append({"role": item.role, "content": content})
        return messages

    def _build_tools_summary(self) -> str:
        """生成可用工具能力摘要。"""
        capabilities: list[str] = []
        for name in self.skill_engine.skill_names():
            if name.startswith("vnpy-data"):
                capabilities.append("数据查询(K线/行情)")
            elif name.startswith("vnpy-backtest"):
                capabilities.append("策略回测")
            elif name.startswith("vnpy-screening"):
                capabilities.append("选股筛选")
            elif name.startswith("vnpy-analysis"):
                capabilities.append("技术形态/策略信号")
            elif name.startswith("tdx-stock-diagnose"):
                capabilities.append("个股诊断(通达信)")
            elif name.startswith("vnpy-watchlist"):
                capabilities.append("自选管理")
            elif name.startswith("vnpy-sentiment"):
                capabilities.append("全市场恐贪指数")
        if capabilities:
            return "\n".join(
                [
                    "【可用工具能力】",
                    "你拥有以下工具能力，涉及行情、K线、财务数据时必须调用工具获取真实数据，禁止编造。",
                    "  " + "、".join(sorted(set(capabilities))),
                ]
            )
        return ""

    def reload_skills(self) -> list[str]:
        self._enabled_skills = self.skill_engine.reload_skills()
        return self._enabled_skills

    def reload_mcp(self) -> list[str]:
        self._enabled_mcp = self.mcp_engine.reload_providers()
        return self._enabled_mcp

    def reload_tools(self) -> tuple[list[str], list[str]]:
        skills = self.reload_skills()
        mcp = self.reload_mcp()
        self._rebind_analysis_mcp()
        self._emit_tools_status()
        return skills, mcp

    def _rebind_analysis_mcp(self) -> None:
        ashare_engine = getattr(self.main_engine, "engines", {}).get("Ashare")
        if ashare_engine is None or not hasattr(ashare_engine, "analysis_service"):
            return
        ashare_engine.analysis_service.bind_mcp(
            self.mcp_engine.execute_tool,
            [spec.name for spec in self.mcp_engine.get_tool_specs()],
        )

    def get_tools_status(self) -> ToolsStatusSnapshot:
        return build_tools_status(self.skill_engine, self.mcp_engine)

    def _emit_tools_status(self) -> None:
        self.signals.tools_status_changed.emit(self.get_tools_status())

    def get_enabled_skills(self) -> list[str]:
        return list(self._enabled_skills)

    def get_enabled_mcp(self) -> list[str]:
        return list(self._enabled_mcp)

    def is_busy(self) -> bool:
        return self._streaming

    def get_current_session_title(self) -> str:
        session = self.store.get_session(self.session_id)
        if session is None:
            return "会话"
        title = session.title.strip()
        return title or "会话"

    def request_cancel_stream(self) -> None:
        """请求中断当前流式回复（由 UI Stop 按钮触发）。"""
        self._cancel_requested = True

    def get_trace_turns(self) -> list[TurnTrace]:
        return self._trace_store.list_turns(self.session_id)

    def get_current_trace_turn(self) -> TurnTrace | None:
        turn = self._trace_store.current_turn()
        if turn is not None and turn.session_id == self.session_id:
            return turn
        return None

    def get_trace_step(self, step_id: str) -> TraceStep | None:
        return self._trace_store.get_step(step_id)

    def format_trace_step_detail(self, step: TraceStep) -> str:
        return self._trace_store.step_detail_json(step)

    def _emit_trace_changed(self) -> None:
        self.signals.trace_changed.emit()

    def _trace_begin_turn(self, user_text: str) -> TurnTrace:
        turn = self._trace_store.start_turn(self.session_id, user_text)
        self._reply_step_id = None
        self._emit_trace_changed()
        return turn

    def _trace_add_routing(self, route_ctx: Any) -> TraceStep:
        route = route_ctx.analysis.route
        summary = f"{route.category} · {route.confidence}"
        if route.reasoning:
            summary = f"{summary} · {route.reasoning[:48]}"
        detail = {
            "category": route.category,
            "confidence": route.confidence,
            "reasoning": route.reasoning,
            "tool_count": len(route_ctx.tools),
            "routing_hint": route_ctx.routing_hint,
            "fear_greed": route_ctx.analysis.market.fear_greed,
            "market_reasoning": route_ctx.analysis.market.reasoning,
        }
        if route_ctx.analysis.screening is not None:
            detail["screening"] = route_ctx.analysis.screening.model_dump()
        if route_ctx.analysis.backtest is not None:
            detail["backtest"] = route_ctx.analysis.backtest.model_dump()
        step = self._trace_store.add_step(
            kind="routing",
            name="intent_route",
            summary=summary,
            detail=detail,
            status="ok",
        )
        self._emit_trace_changed()
        return step

    def _trace_begin_tool(self, name: str, arguments: dict[str, Any]) -> str:
        display = tool_display_name(name)
        step = self._trace_store.add_step(
            kind="tool",
            name=name,
            summary=f"{display}…",
            detail={"arguments": arguments},
        )
        self._emit_trace_changed()
        return step.id

    def _trace_finish_tool(
        self,
        step_id: str,
        *,
        result: str,
        success: bool,
    ) -> None:
        step = self._trace_store.get_step(step_id)
        if step is None:
            return
        display = tool_display_name(step.name)
        status = "ok" if success else "error"
        summary = display if success else f"{display} 失败"
        self._trace_store.update_step(
            step_id,
            status=status,
            summary=summary,
            detail={"result_preview": preview_text(result)},
        )
        self._emit_trace_changed()

    def _trace_begin_reply(self) -> None:
        if self._reply_step_id is not None:
            return
        step = self._trace_store.add_step(
            kind="reply",
            name="assistant_reply",
            summary="生成回复…",
        )
        self._reply_step_id = step.id
        self._emit_trace_changed()

    def _trace_finish_reply(self) -> None:
        if self._reply_step_id is None:
            return
        self._trace_store.update_step(
            self._reply_step_id,
            status="ok",
            summary="回复完成",
        )
        self._reply_step_id = None
        self._emit_trace_changed()

    def _trace_add_error(self, message: str) -> None:
        if self._trace_store.current_turn() is None:
            return
        self._trace_store.add_step(
            kind="error",
            name="stream_error",
            summary=message[:80],
            detail={"message": message},
            status="error",
        )
        self._emit_trace_changed()

    def _trace_finish_turn(self, *, ok: bool) -> None:
        if self._reply_step_id is not None:
            self._trace_store.update_step(
                self._reply_step_id,
                status="error" if not ok else "ok",
                summary="回复中断" if not ok else "回复完成",
            )
            self._reply_step_id = None
        self._trace_store.finish_turn("ok" if ok else "error")
        self._emit_trace_changed()

    def _get_openai_tools(self) -> list[dict[str, Any]]:
        tools = self.skill_engine.get_openai_tools()
        tools.extend(self.mcp_engine.get_openai_tools())
        return tools

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        step_id = self._trace_begin_tool(name, arguments)
        self.signals.tool_call_started.emit(name)
        result = ""
        success = True
        try:
            mcp_names = {spec.name for spec in self.mcp_engine.get_tool_specs()}
            if name in mcp_names:
                result = self.mcp_engine.execute_tool(name, arguments)
            else:
                result = self.skill_engine.execute_tool(name, arguments)
            if name == "propose_screening":
                self._maybe_emit_screener_draft(result)
            if name == "propose_recipe":
                self._maybe_emit_recipe_draft(result)
            return enrich_tool_result(result)
        except Exception as ex:
            success = False
            result = enrich_tool_result(json.dumps({"error": str(ex)}, ensure_ascii=False))
            return result
        finally:
            self._trace_finish_tool(step_id, result=result, success=success)
            try:
                if result:
                    log_tool_call(
                        session_id=self.session_id,
                        tool_name=name,
                        arguments=arguments,
                        result=result,
                        success=success,
                    )
            except Exception:
                pass
            self.signals.tool_call_finished.emit(name)

    def _maybe_emit_screener_draft(self, result: str) -> None:
        self._maybe_emit_draft_signal(result, signal_name="screener_draft_ready")

    def _maybe_emit_recipe_draft(self, result: str) -> None:
        self._maybe_emit_draft_signal(result, signal_name="recipe_draft_ready")

    def _maybe_emit_draft_signal(self, result: str, *, signal_name: str) -> None:
        try:
            payload = json.loads(result)
        except json.JSONDecodeError:
            return
        if payload.get("status") != "pending_confirm":
            return
        draft_id = payload.get("draft_id")
        if isinstance(draft_id, str) and draft_id:
            signal = getattr(self.signals, signal_name, None)
            if signal is not None:
                signal.emit(draft_id)

    def append_local_message(self, *, role: str, content: str) -> None:
        if role == "user":
            self._maybe_update_session_title(content)
        self.store.append_message(self.session_id, role=role, content=content)
        self.signals.messages_changed.emit()
        self.signals.sessions_changed.emit()

    def stream_reply(self, user_text: str) -> Iterator[str]:
        if self._streaming:
            raise LlmClientError("上一条回复仍在生成中")
        self._streaming = True
        self._cancel_requested = False
        self.signals.stream_started.emit()
        self.append_local_message(role="user", content=user_text)
        self._trace_begin_turn(user_text)
        turn_ok = True
        cancelled = False

        def should_cancel() -> bool:
            return self._cancel_requested

        chunks: list[str] = []

        def _persist_partial() -> None:
            content = "".join(chunks).strip()
            if content:
                self.append_local_message(role="assistant", content=content)

        try:
            all_tools = self._get_openai_tools()
            if all_tools:
                mcp_names = frozenset(spec.name for spec in self.mcp_engine.get_tool_specs())
                route_ctx = build_route_context(
                    self.config,
                    user_text,
                    all_tools,
                    page=get_ai_context().page,
                    mcp_tool_names=mcp_names,
                )
                self._trace_add_routing(route_ctx)
                messages = self.build_api_messages(extra_system=route_ctx.routing_hint)
                chunks = []
                self._trace_begin_reply()
                for delta in stream_with_tools(
                    self.config,
                    messages,
                    route_ctx.tools,
                    self._execute_tool,
                    should_cancel=should_cancel,
                ):
                    chunks.append(delta)
                    self.signals.stream_delta.emit(delta)
                    yield delta
                content = "".join(chunks).strip()
                if content:
                    self.append_local_message(role="assistant", content=content)
            else:
                chunks = []
                self._trace_begin_reply()
                for delta in stream_chat_completion(
                    self.config,
                    self.build_api_messages(),
                    should_cancel=should_cancel,
                ):
                    chunks.append(delta)
                    self.signals.stream_delta.emit(delta)
                    yield delta
                content = "".join(chunks).strip()
                if content:
                    self.append_local_message(role="assistant", content=content)
            self._trace_finish_reply()
        except StreamCancelled:
            cancelled = True
            turn_ok = False
            _persist_partial()
            self.signals.stream_cancelled.emit()
        except Exception as ex:
            turn_ok = False
            self._trace_add_error(str(ex))
            self.signals.stream_failed.emit(str(ex))
            raise
        finally:
            self._streaming = False
            self._cancel_requested = False
            if not cancelled:
                self._trace_finish_turn(ok=turn_ok)
            self.signals.stream_finished.emit()

    def reload_config(self) -> LlmConfig:
        """从 .env 重新加载 LLM 配置（无需重启 GUI）。"""
        from dotenv import load_dotenv

        from vnpy_common.paths import ENV_FILE

        if ENV_FILE.is_file():
            load_dotenv(ENV_FILE, override=True)
        self.config = load_llm_config()
        return self.config

    def close(self) -> None:
        self._bind_surface_session(self._active_surface, self.session_id)
        super().close()
