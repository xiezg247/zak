"""会话持久化。"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CHAT_DB_PATH = Path.home() / ".vntrader" / "llm_chat.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
"""


@dataclass
class ChatMessage:
    role: str
    content: str
    created_at: str = ""


@contextmanager
def _connect():
    CHAT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CHAT_DB_PATH)
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


MAX_MESSAGES_PER_SESSION = 50
MAX_TOOL_RESULT_CHARS = 2000

class ChatStore:
    def get_or_create_default_session(self) -> str:
        with _connect() as conn:
            row = conn.execute(
                "SELECT id FROM sessions ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
            if row:
                return str(row["id"])
            session_id = uuid.uuid4().hex
            now = _now()
            conn.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, "默认会话", now, now),
            )
            return session_id

    def create_session(self, *, title: str = "新会话") -> str:
        session_id = uuid.uuid4().hex
        now = _now()
        with _connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, title, now, now),
            )
        return session_id

    def list_messages(self, session_id: str) -> list[ChatMessage]:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM messages WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
        messages = [
            ChatMessage(role=str(row["role"]), content=str(row["content"]), created_at=str(row["created_at"]))
            for row in rows
        ]
        if len(messages) > MAX_MESSAGES_PER_SESSION:
            messages = messages[-MAX_MESSAGES_PER_SESSION:]
        return messages

    def append_message(self, session_id: str, *, role: str, content: str) -> None:
        now = _now()
        with _connect() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at=? WHERE id=?",
                (now, session_id),
            )

    def clear_messages(self, session_id: str) -> None:
        with _connect() as conn:
            conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
