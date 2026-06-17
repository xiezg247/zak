"""AI 对话会话 SQLite 持久化（~/.vntrader/llm_chat.db）。"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import cast

from vnpy_common.paths import get_chat_db_path
from vnpy_llm.domain.chat import ChatMessage, ChatSession


# 测试可 patch 此函数
def _chat_db_path() -> Path:
    return cast(Path, get_chat_db_path())


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    scene TEXT NOT NULL DEFAULT '',
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


@contextmanager
def _connect():
    path = _chat_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        _ensure_session_columns(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_session_columns(conn: sqlite3.Connection) -> None:
    columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
    if "scene" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN scene TEXT NOT NULL DEFAULT ''")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


MAX_MESSAGES_PER_SESSION = 50
MAX_TOOL_RESULT_CHARS = 2000


class ChatStore:
    """会话与消息的 CRUD；单会话最多保留 MAX_MESSAGES_PER_SESSION 条。"""

    def get_or_create_default_session(self) -> str:
        """获取最近会话 id，无则创建「默认会话」。"""
        with _connect() as conn:
            row = conn.execute("SELECT id FROM sessions ORDER BY updated_at DESC LIMIT 1").fetchone()
            if row:
                return str(row["id"])
            session_id = uuid.uuid4().hex
            now = _now()
            conn.execute(
                "INSERT INTO sessions (id, title, scene, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, "默认会话", "", now, now),
            )
            return session_id

    def create_session(self, *, title: str = "新会话", scene: str = "") -> str:
        """创建新会话并返回 id。"""
        session_id = uuid.uuid4().hex
        now = _now()
        with _connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, scene, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, title, scene.strip(), now, now),
            )
        return session_id

    def list_sessions(self, *, limit: int = 50) -> list[ChatSession]:
        """按更新时间倒序列出会话。"""
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.title, s.scene, s.created_at, s.updated_at,
                       COUNT(m.id) AS message_count
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                GROUP BY s.id
                ORDER BY s.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            ChatSession.model_validate(
                {
                    "id": str(row["id"]),
                    "title": str(row["title"] or "新会话"),
                    "created_at": str(row["created_at"]),
                    "updated_at": str(row["updated_at"]),
                    "message_count": int(row["message_count"]),
                    "scene": str(row["scene"] or ""),
                }
            )
            for row in rows
        ]

    def get_session(self, session_id: str) -> ChatSession | None:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT s.id, s.title, s.scene, s.created_at, s.updated_at,
                       COUNT(m.id) AS message_count
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                WHERE s.id = ?
                GROUP BY s.id
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return ChatSession.model_validate(
            {
                "id": str(row["id"]),
                "title": str(row["title"] or "新会话"),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
                "message_count": int(row["message_count"]),
                "scene": str(row["scene"] or ""),
            }
        )

    def update_session_scene(self, session_id: str, scene: str) -> None:
        cleaned = scene.strip()
        with _connect() as conn:
            conn.execute(
                "UPDATE sessions SET scene=? WHERE id=?",
                (cleaned, session_id),
            )

    def update_session_title(self, session_id: str, title: str) -> None:
        cleaned = title.strip() or "新会话"
        with _connect() as conn:
            conn.execute(
                "UPDATE sessions SET title=? WHERE id=?",
                (cleaned, session_id),
            )

    def delete_session(self, session_id: str) -> None:
        with _connect() as conn:
            conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))

    def list_messages(self, session_id: str) -> list[ChatMessage]:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM messages WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
        messages = [
            ChatMessage.model_validate(
                {
                    "role": str(row["role"]),
                    "content": str(row["content"]),
                    "created_at": str(row["created_at"]),
                }
            )
            for row in rows
        ]
        if len(messages) > MAX_MESSAGES_PER_SESSION:
            messages = messages[-MAX_MESSAGES_PER_SESSION:]
        return messages

    def append_message(self, session_id: str, *, role: str, content: str) -> None:
        """追加消息并刷新会话 updated_at。"""
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
