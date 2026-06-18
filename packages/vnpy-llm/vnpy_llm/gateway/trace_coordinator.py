"""Turn Trace 生命周期协调（路由 / 工具 / 回复 / handoff）。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from vnpy_llm.graph.supervisor import build_supervisor_decision
from vnpy_llm.tools.labels import tool_display_name
from vnpy_llm.trace.persistence import TracePersistence
from vnpy_llm.trace.trace import TraceStep, TraceStore, TurnTrace, preview_text
from vnpy_common.domain.serialize import dump_json

TraceChanged = Callable[[], None]


class TraceCoordinator:
    """封装 TraceStore 与单轮 reply step 状态。"""

    def __init__(
        self,
        *,
        store: TraceStore | None = None,
        on_changed: TraceChanged | None = None,
    ) -> None:
        self._store = store or TraceStore(TracePersistence())
        self._on_changed = on_changed
        self._reply_step_id: str | None = None

    @property
    def store(self) -> TraceStore:
        return self._store

    def _emit_changed(self) -> None:
        if self._on_changed is not None:
            self._on_changed()

    def ensure_session_loaded(self, session_id: str) -> None:
        self._store.ensure_session_loaded(session_id)

    def clear_session(self, session_id: str) -> None:
        self._store.clear_session(session_id)

    def list_turns(self, session_id: str) -> list[TurnTrace]:
        return self._store.list_turns(session_id)

    def current_turn_for_session(self, session_id: str) -> TurnTrace | None:
        turn = self._store.current_turn()
        if turn is not None and turn.session_id == session_id:
            return turn
        return None

    def get_step(self, step_id: str) -> TraceStep | None:
        return self._store.get_step(step_id)

    def format_step_detail(self, step: TraceStep) -> str:
        return self._store.step_detail_json(step)

    def begin_turn(self, session_id: str, user_text: str) -> TurnTrace:
        turn = self._store.start_turn(session_id, user_text)
        self._reply_step_id = None
        self._emit_changed()
        return turn

    def on_handoff(self, from_agent: str, to_agent: str, reason: str) -> None:
        if self._store.current_turn() is None:
            return
        self._store.add_step(
            kind="handoff",
            name=f"{from_agent}->{to_agent}",
            summary=(reason or f"{from_agent} → {to_agent}")[:80],
            detail={"from_agent": from_agent, "to_agent": to_agent, "reason": reason},
            status="ok",
        )
        self._emit_changed()

    def add_routing(
        self,
        route_ctx: Any,
        *,
        user_text: str = "",
        supervisor: Any | None = None,
    ) -> TraceStep:
        route = route_ctx.analysis.route
        decision = supervisor or build_supervisor_decision(route_ctx.analysis, user_text)
        summary = f"{route.category} → {decision.target_agent} · {route.confidence}"
        if route.reasoning:
            summary = f"{summary} · {route.reasoning[:48]}"
        detail = {
            "category": route.category,
            "target_agent": decision.target_agent,
            "handoff_agents": decision.handoff_agents,
            "confidence": route.confidence,
            "reasoning": route.reasoning,
            "tool_count": len(route_ctx.tools),
            "routing_hint": route_ctx.routing_hint,
            "fear_greed": route_ctx.analysis.market.fear_greed,
            "market_reasoning": route_ctx.analysis.market.reasoning,
        }
        if route_ctx.analysis.screening is not None:
            detail["screening"] = dump_json(route_ctx.analysis.screening)
        if route_ctx.analysis.backtest is not None:
            detail["backtest"] = dump_json(route_ctx.analysis.backtest)
        step = self._store.add_step(
            kind="routing",
            name="intent_route",
            summary=summary,
            detail=detail,
            status="ok",
        )
        self._emit_changed()
        return step

    def begin_tool(self, name: str, arguments: dict[str, Any]) -> str:
        display = tool_display_name(name)
        step = self._store.add_step(
            kind="tool",
            name=name,
            summary=f"{display}…",
            detail={"arguments": arguments},
        )
        self._emit_changed()
        return step.id

    def finish_tool(self, step_id: str, *, result: str, success: bool) -> None:
        step = self._store.get_step(step_id)
        if step is None:
            return
        display = tool_display_name(step.name)
        trace_status: Literal["ok", "error"] = "ok" if success else "error"
        summary = display if success else f"{display} 失败"
        self._store.update_step(
            step_id,
            status=trace_status,
            summary=summary,
            detail={"result_preview": preview_text(result)},
        )
        self._emit_changed()

    def begin_reply(self) -> None:
        if self._reply_step_id is not None:
            return
        step = self._store.add_step(
            kind="reply",
            name="assistant_reply",
            summary="生成回复…",
        )
        self._reply_step_id = step.id
        self._emit_changed()

    def finish_reply(self) -> None:
        if self._reply_step_id is None:
            return
        self._store.update_step(
            self._reply_step_id,
            status="ok",
            summary="回复完成",
        )
        self._reply_step_id = None
        self._emit_changed()

    def add_error(self, message: str) -> None:
        if self._store.current_turn() is None:
            return
        self._store.add_step(
            kind="error",
            name="stream_error",
            summary=message[:80],
            detail={"message": message},
            status="error",
        )
        self._emit_changed()

    def begin_team_step(self, name: str, summary: str, *, detail: dict[str, Any] | None = None) -> str:
        step = self._store.add_step(
            kind="team",
            name=name,
            summary=summary[:80],
            detail=detail or {},
        )
        self._emit_changed()
        return step.id

    def finish_team_step(
        self,
        step_id: str,
        *,
        summary: str,
        ok: bool = True,
        detail: dict[str, Any] | None = None,
    ) -> None:
        trace_status: Literal["ok", "error"] = "ok" if ok else "error"
        payload: dict[str, Any] = {}
        if detail:
            payload.update(detail)
        self._store.update_step(
            step_id,
            status=trace_status,
            summary=summary[:80],
            detail=payload or None,
        )
        self._emit_changed()

    def finish_turn(self, *, ok: bool) -> None:
        if self._reply_step_id is not None:
            self._store.update_step(
                self._reply_step_id,
                status="error" if not ok else "ok",
                summary="回复中断" if not ok else "回复完成",
            )
            self._reply_step_id = None
        self._store.finish_turn("ok" if ok else "error")
        self._emit_changed()
