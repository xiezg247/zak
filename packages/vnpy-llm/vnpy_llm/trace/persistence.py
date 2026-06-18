"""Trace 调用链路 SQLite 持久化（与 llm_chat.db 同库）。"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from pydantic import ValidationError

import vnpy_llm.chat.store as store
from vnpy_llm.trace.trace import TurnTrace, turn_from_dict, turn_to_dict

MAX_TURNS_PER_SESSION = 50

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_turn_traces (
    turn_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    user_text TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    trace_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_turn_traces_session
    ON llm_turn_traces(session_id, turn_index);
"""


@contextmanager
def _connect():
    path = store._chat_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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


class TracePersistence:
    """按 session 读写 TurnTrace。"""

    def load_turns(self, session_id: str) -> list[TurnTrace]:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT trace_json
                FROM llm_turn_traces
                WHERE session_id=?
                ORDER BY turn_index ASC, created_at ASC
                """,
                (session_id,),
            ).fetchall()

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
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO llm_turn_traces
                (turn_id, session_id, turn_index, user_text, status, created_at, updated_at, trace_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(turn_id) DO UPDATE SET
                    session_id=excluded.session_id,
                    turn_index=excluded.turn_index,
                    user_text=excluded.user_text,
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    trace_json=excluded.trace_json
                """,
                (
                    turn.turn_id,
                    turn.session_id,
                    turn_index,
                    turn.user_text,
                    turn.status,
                    created_at,
                    now,
                    trace_json,
                ),
            )
            self._prune_session(conn, turn.session_id)

    def delete_session(self, session_id: str) -> None:
        with _connect() as conn:
            conn.execute("DELETE FROM llm_turn_traces WHERE session_id=?", (session_id,))

    def _prune_session(self, conn: sqlite3.Connection, session_id: str) -> None:
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt FROM llm_turn_traces WHERE session_id=?
            """,
            (session_id,),
        ).fetchone()
        count = int(row["cnt"]) if row else 0
        if count <= MAX_TURNS_PER_SESSION:
            return
        overflow = count - MAX_TURNS_PER_SESSION
        conn.execute(
            """
            DELETE FROM llm_turn_traces
            WHERE turn_id IN (
                SELECT turn_id FROM llm_turn_traces
                WHERE session_id=?
                ORDER BY turn_index ASC, created_at ASC
                LIMIT ?
            )
            """,
            (session_id, overflow),
        )
