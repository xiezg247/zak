"""Trace 调用链路持久化（与 chat 库同库）。"""

from __future__ import annotations

import json
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from vnpy_common.storage.tables.chat import llm_turn_traces as ltt
from vnpy_llm.storage.repository.chat import ChatUserScopedRepository
from vnpy_llm.trace.trace import TurnTrace, turn_from_dict, turn_to_dict

MAX_TURNS_PER_SESSION = 50


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _repair_interrupted_turn(turn: TurnTrace) -> TurnTrace:
    if turn.status != "running":
        return turn
    turn.status = "error"
    for step in turn.steps:
        if step.status == "running":
            step.status = "error"
            step.summary = f"{step.summary.rstrip('…')} 中断"
    return turn


class TraceRepository(ChatUserScopedRepository):
    """按 session 读写 TurnTrace。"""

    table = ltt

    def load_turns(self, session_id: str) -> list[TurnTrace]:
        rows = self.fetchall(
            select(ltt.c.trace_json).where(self.scope(ltt.c.session_id == session_id)).order_by(ltt.c.turn_index.asc(), ltt.c.created_at.asc())
        )

        turns: list[TurnTrace] = []
        for i, row in enumerate(rows):
            try:
                payload = json.loads(str(row["trace_json"]))
                turn = turn_from_dict(payload)
            except (json.JSONDecodeError, KeyError, TypeError, ValidationError):
                continue
            if turn.session_id != session_id:
                turn.session_id = session_id
            repaired = _repair_interrupted_turn(turn)
            if repaired.status == "error" and turn.status == "running":
                self.save_turn(repaired, turn_index=i)
            turns.append(repaired)
        if len(turns) > MAX_TURNS_PER_SESSION:
            turns = turns[-MAX_TURNS_PER_SESSION:]
        return turns

    def save_turn(self, turn: TurnTrace, *, turn_index: int) -> None:
        now = _now()
        created_at = turn.created_at or now
        trace_json = json.dumps(turn_to_dict(turn), ensure_ascii=False)
        values = {
            "turn_id": turn.turn_id,
            "session_id": turn.session_id,
            "turn_index": turn_index,
            "user_text": turn.user_text,
            "status": turn.status,
            "created_at": created_at,
            "updated_at": now,
            "trace_json": trace_json,
            "user_id": self.current_user_id(),
        }

        def _write(conn) -> None:
            stmt = pg_insert(ltt).values(values)
            excluded = stmt.excluded
            conn.execute_stmt(
                stmt.on_conflict_do_update(
                    index_elements=[ltt.c.turn_id],
                    set_={
                        "session_id": excluded.session_id,
                        "turn_index": excluded.turn_index,
                        "user_text": excluded.user_text,
                        "status": excluded.status,
                        "updated_at": excluded.updated_at,
                        "trace_json": excluded.trace_json,
                        "user_id": excluded.user_id,
                    },
                )
            )
            self._prune_session(conn, turn.session_id)

        self.run(_write)

    def delete_session(self, session_id: str) -> None:
        self.delete_matching(self.scope(ltt.c.session_id == session_id))

    def _prune_session(self, conn, session_id: str) -> None:
        scope = self.scope(ltt.c.session_id == session_id)
        row = conn.execute_stmt(select(func.count()).select_from(ltt).where(scope)).fetchone()
        count = int(row[0]) if row is not None else 0
        if count <= MAX_TURNS_PER_SESSION:
            return
        overflow = count - MAX_TURNS_PER_SESSION
        subq = select(ltt.c.turn_id).where(scope).order_by(ltt.c.turn_index.asc(), ltt.c.created_at.asc()).limit(overflow)
        conn.execute_stmt(delete(ltt).where(ltt.c.turn_id.in_(subq)))


class TracePersistence(TraceRepository):
    """按 session 读写 TurnTrace（对外兼容名）。"""
