"""大模型引擎。"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from typing import Any

from vnpy.event import EventEngine
from vnpy.trader.engine import BaseEngine, MainEngine
from vnpy.trader.ui import QtCore

from vnpy_llm.client import LlmClientError, complete_with_tools, stream_chat_completion
from vnpy_llm.config import LlmConfig, load_llm_config
from vnpy_llm.prompts import SYSTEM_PROMPT, build_page_prompt, build_strategy_prompt
from vnpy_llm.session_surface import SessionSurfaceStore, Surface
from vnpy_llm.store import MAX_MESSAGES_PER_SESSION, MAX_TOOL_RESULT_CHARS, ChatMessage, ChatSession, ChatStore
from vnpy_llm.tools_status import ToolsStatusSnapshot, build_tools_status
from vnpy_mcp import McpEngine
from vnpy_skills import SkillEngine

from vnpy_ashare.ai.context import AiContextData
from vnpy_ashare.ai.session_context import register_context_listener, sync_backtest_to_service

APP_NAME = "Llm"


class LlmSignals(QtCore.QObject):
    messages_changed = QtCore.Signal()
    sessions_changed = QtCore.Signal()
    stream_started = QtCore.Signal()
    stream_delta = QtCore.Signal(str)
    stream_finished = QtCore.Signal()
    stream_failed = QtCore.Signal(str)
    context_changed = QtCore.Signal(str)
    tools_status_changed = QtCore.Signal(object)
    tool_call_started = QtCore.Signal(str)
    tool_call_finished = QtCore.Signal(str)
    screener_draft_ready = QtCore.Signal(str)


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
            sync_backtest_to_service(ashare_engine.backtest_service)
        self.register_event()
        register_context_listener(self._on_session_context_changed)
        self._emit_tools_status()

    def _on_session_context_changed(self, data: AiContextData) -> None:
        self.signals.context_changed.emit(data.to_text())

    def register_event(self) -> None:
        pass  # EVENT_AI_CONTEXT 已移除，改用 session_context 桥接

    def set_extra_context_provider(self, provider: Callable[[], str] | None) -> None:
        self._extra_context_provider = provider

    def get_context_text(self) -> str:
        parts: list[str] = []
        # 从 session_context 读取（QuotesPage 通过 set_ai_context 写入）
        from vnpy_ashare.ai.session_context import get_ai_context
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
            self.signals.messages_changed.emit()
            self.signals.sessions_changed.emit()

    def open_session_for_ask(
        self,
        *,
        surface: Surface,
        new_session: bool = False,
        session_policy: str = "resume",
        scene: str = "",
    ) -> str:
        """打开悬浮/全屏 AI 前的统一会话入口。"""
        _ = scene  # 预留 scene 策略（Phase 2）
        self.switch_surface(surface)
        if new_session or session_policy == "new":
            return self.new_session(surface=surface)
        return self.session_id

    def switch_session(self, session_id: str) -> None:
        if session_id == self.session_id:
            return
        if self.store.get_session(session_id) is None:
            return
        self.session_id = session_id
        self._bind_surface_session(self._active_surface, session_id)
        self.signals.messages_changed.emit()
        self.signals.sessions_changed.emit()

    def rename_session(self, session_id: str, title: str) -> None:
        self.store.update_session_title(session_id, title)
        self.signals.sessions_changed.emit()

    def delete_session(self, session_id: str) -> None:
        self.store.delete_session(session_id)
        remaining = self.store.list_sessions(limit=1)
        replacement = remaining[0].id if remaining else self.store.create_session()
        self._surface_store.clear_binding(session_id, replacement=replacement)
        if session_id == self.session_id:
            self.session_id = self._ensure_session_exists(
                self._surface_store.get(self._active_surface, fallback=replacement),
            )
            self._bind_surface_session(self._active_surface, self.session_id)
            self.signals.messages_changed.emit()
        self.signals.sessions_changed.emit()

    def clear_session(self) -> None:
        self.store.clear_messages(self.session_id)
        self.signals.messages_changed.emit()
        self.signals.sessions_changed.emit()

    def new_session(
        self,
        *,
        title: str = "新会话",
        surface: Surface | None = None,
    ) -> str:
        target = surface or self._active_surface
        session_id = self.store.create_session(title=title)
        self._bind_surface_session(target, session_id)
        if target == self._active_surface:
            self.session_id = session_id
            self.signals.messages_changed.emit()
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

    def build_api_messages(self) -> list[dict[str, str]]:
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
        from vnpy_ashare.ai.session_context import get_ai_context

        page_prompt = build_page_prompt(get_ai_context().page)
        if page_prompt:
            system_parts.append(page_prompt)
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
                capabilities.append("股票诊断")
            elif name.startswith("vnpy-watchlist"):
                capabilities.append("自选管理")
        if capabilities:
            return "\n".join([
                "【可用工具能力】",
                "你拥有以下工具能力，涉及行情、K线、财务数据时必须调用工具获取真实数据，禁止编造。",
                "  " + "、".join(sorted(set(capabilities))),
            ])
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

    def _get_openai_tools(self) -> list[dict[str, Any]]:
        tools = self.skill_engine.get_openai_tools()
        tools.extend(self.mcp_engine.get_openai_tools())
        return tools

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
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
            return result
        except Exception as ex:
            success = False
            result = json.dumps({"error": str(ex)}, ensure_ascii=False)
            raise
        finally:
            try:
                from vnpy_llm.tool_audit import log_tool_call

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
        try:
            payload = json.loads(result)
        except json.JSONDecodeError:
            return
        if payload.get("status") != "pending_confirm":
            return
        draft_id = payload.get("draft_id")
        if isinstance(draft_id, str) and draft_id:
            self.signals.screener_draft_ready.emit(draft_id)

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
        self._bind_surface_session(self._active_surface, self.session_id)
        super().close()
