"""AI 助手调用链路 Trace（内存 + SQLite 持久化）。"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from vnpy_common.ai.protocol import AiChartSpec
from vnpy_llm.domain.trace import TraceKind, TraceStatus, TraceStep, TurnStatus, TurnTrace
from vnpy_llm.tools.chart_collector import merge_chart_attachment

if TYPE_CHECKING:
    from vnpy_llm.trace.persistence import TracePersistence

_PREVIEW_MAX = 600

__all__ = [
    "TraceKind",
    "TraceStatus",
    "TraceStep",
    "TurnStatus",
    "TurnTrace",
    "TraceStore",
    "map_turns_to_user_messages",
    "preview_text",
    "step_from_dict",
    "step_to_dict",
    "turn_from_dict",
    "turn_to_dict",
]


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def preview_text(text: str, *, limit: int = _PREVIEW_MAX) -> str:
    """截断过长文本用于 Trace 摘要展示。"""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def map_turns_to_user_messages(
    messages: list[Any],
    turns: list[TurnTrace],
) -> dict[int, TurnTrace]:
    """将 Trace 轮次对齐到 user 消息（优先文本匹配，否则从末尾配对）。"""
    user_entries = [(index, str(msg.content).strip()) for index, msg in enumerate(messages) if getattr(msg, "role", "") == "user"]
    if not user_entries or not turns:
        return {}

    mapping: dict[int, TurnTrace] = {}
    used_turn_ids: set[str] = set()

    for msg_index, text in user_entries:
        if not text:
            continue
        for turn in reversed(turns):
            if turn.turn_id in used_turn_ids:
                continue
            if turn.user_text.strip() == text:
                mapping[msg_index] = turn
                used_turn_ids.add(turn.turn_id)
                break

    unused_turns = [turn for turn in turns if turn.turn_id not in used_turn_ids]
    unmatched_users = [entry for entry in user_entries if entry[0] not in mapping]
    pair_count = min(len(unused_turns), len(unmatched_users))
    for offset in range(pair_count):
        msg_index = unmatched_users[len(unmatched_users) - pair_count + offset][0]
        mapping[msg_index] = unused_turns[len(unused_turns) - pair_count + offset]
    return mapping


def step_to_dict(step: TraceStep) -> dict[str, Any]:
    """TraceStep → SQLite 持久化 dict。"""
    return step.persist_dict()


def step_from_dict(data: dict[str, Any]) -> TraceStep:
    """dict → TraceStep。"""
    return TraceStep.model_validate(data)


def turn_to_dict(turn: TurnTrace) -> dict[str, Any]:
    """TurnTrace → SQLite 持久化 dict。"""
    return turn.persist_dict()


def turn_from_dict(data: dict[str, Any]) -> TurnTrace:
    """dict → TurnTrace。"""
    return TurnTrace.from_persist_dict(data)


class TraceStore:
    """按 session 保存 TurnTrace，支持当前轮次实时更新与持久化。"""

    def __init__(self, persistence: TracePersistence | None = None) -> None:
        self._persistence = persistence
        self._turns: dict[str, list[TurnTrace]] = {}
        self._current: TurnTrace | None = None
        self._step_index: dict[str, TraceStep] = {}
        self._loaded_sessions: set[str] = set()

    def ensure_session_loaded(self, session_id: str) -> None:
        if session_id in self._loaded_sessions:
            return
        if self._persistence is not None:
            turns = self._persistence.load_turns(session_id)
            self._turns[session_id] = turns
            for turn in turns:
                for step in turn.steps:
                    self._step_index[step.id] = step
        else:
            self._turns.setdefault(session_id, [])
        self._loaded_sessions.add(session_id)

    def current_turn(self) -> TurnTrace | None:
        return self._current

    def list_turns(self, session_id: str) -> list[TurnTrace]:
        self.ensure_session_loaded(session_id)
        return list(self._turns.get(session_id, []))

    def get_step(self, step_id: str) -> TraceStep | None:
        return self._step_index.get(step_id)

    def start_turn(self, session_id: str, user_text: str) -> TurnTrace:
        self.ensure_session_loaded(session_id)
        turn = TurnTrace(
            turn_id=uuid.uuid4().hex[:12],
            session_id=session_id,
            user_text=user_text.strip(),
            started_at=time.monotonic(),
            created_at=_now_str(),
        )
        self._current = turn
        self._turns.setdefault(session_id, []).append(turn)
        self._persist_turn(turn)
        return turn

    def finish_turn(self, status: TurnStatus = "ok") -> TurnTrace | None:
        if self._current is None:
            return None
        self._current.status = status
        finished = self._current
        self._current = None
        self._persist_turn(finished)
        return finished

    def add_step(
        self,
        *,
        kind: TraceKind,
        name: str,
        summary: str,
        detail: dict[str, Any] | None = None,
        status: TraceStatus = "running",
    ) -> TraceStep:
        if self._current is None:
            raise RuntimeError("no active turn")
        step = TraceStep(
            id=uuid.uuid4().hex[:12],
            turn_id=self._current.turn_id,
            kind=kind,
            name=name,
            status=status,
            summary=summary,
            detail=dict(detail or {}),
            started_at=time.monotonic(),
        )
        self._current.steps.append(step)
        self._step_index[step.id] = step
        if status in ("ok", "error"):
            step.duration_ms = 0
        self._persist_turn(self._current)
        return step

    def update_step(
        self,
        step_id: str,
        *,
        status: TraceStatus | None = None,
        summary: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> TraceStep | None:
        step = self._step_index.get(step_id)
        if step is None:
            return None
        if status is not None:
            step.status = status
        if summary is not None:
            step.summary = summary
        if detail:
            step.detail.update(detail)
        if status in ("ok", "error") and step.duration_ms is None:
            step.duration_ms = max(0, int((time.monotonic() - step.started_at) * 1000))
        turn = self._turn_for_step(step)
        if turn is not None:
            self._persist_turn(turn)
        return step

    def add_chart_attachment(self, spec: AiChartSpec) -> None:
        if self._current is None:
            return
        self._current.attachments = merge_chart_attachment(self._current.attachments, spec)
        self._persist_turn(self._current)

    def clear_session(self, session_id: str) -> None:
        removed = self._turns.pop(session_id, [])
        removed_ids = {t.turn_id for t in removed}
        if self._current is not None and self._current.session_id == session_id:
            removed_ids.add(self._current.turn_id)
            self._current = None
        if removed_ids:
            self._step_index = {sid: step for sid, step in self._step_index.items() if step.turn_id not in removed_ids}
        self._loaded_sessions.discard(session_id)
        if self._persistence is not None:
            self._persistence.delete_session(session_id)

    def _turn_for_step(self, step: TraceStep) -> TurnTrace | None:
        if self._current is not None and self._current.turn_id == step.turn_id:
            return self._current
        for turns in self._turns.values():
            for turn in turns:
                if turn.turn_id == step.turn_id:
                    return turn
        return None

    def _persist_turn(self, turn: TurnTrace) -> None:
        if self._persistence is None:
            return
        turns = self._turns.get(turn.session_id, [])
        try:
            turn_index = turns.index(turn)
        except ValueError:
            turn_index = len(turns) - 1
        self._persistence.save_turn(turn, turn_index=max(0, turn_index))

    def step_detail_json(self, step: TraceStep) -> str:
        payload = {
            "kind": step.kind,
            "name": step.name,
            "status": step.status,
            "summary": step.summary,
            "duration_ms": step.duration_ms,
            "detail": step.detail,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
