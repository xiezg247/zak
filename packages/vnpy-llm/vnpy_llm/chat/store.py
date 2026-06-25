"""AI 对话会话持久化（PostgreSQL chat schema）。"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime

from vnpy_ashare.storage.auth.scope import get_user_id
from vnpy_llm.domain.chat import ChatMessage, ChatSession
from vnpy_common.storage.session import chat_session


@contextmanager
def _connect():
    with chat_session() as conn:
        yield conn


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


MAX_MESSAGES_PER_SESSION = 50
MAX_TOOL_RESULT_CHARS = 2000


class ChatStore:
    """会话与消息的 CRUD；单会话最多保留 MAX_MESSAGES_PER_SESSION 条。"""

    def get_or_create_default_session(self) -> str:
        """获取最近会话 id，无则创建「默认会话」。"""
        uid = get_user_id()
        with _connect() as conn:
            row = conn.execute(
                "SELECT id FROM sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
                (uid,),
            ).fetchone()
            if row is not None:
                return str(row["id"])
            session_id = uuid.uuid4().hex
            now = _now()
            conn.execute(
                "INSERT INTO sessions (id, title, scene, created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, "默认会话", "", now, now, uid),
            )
            return session_id

    def create_session(self, *, title: str = "新会话", scene: str = "") -> str:
        """创建新会话并返回 id。"""
        uid = get_user_id()
        session_id = uuid.uuid4().hex
        now = _now()
        with _connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, scene, created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, title, scene.strip(), now, now, uid),
            )
        return session_id

    def list_sessions(self, *, limit: int = 50) -> list[ChatSession]:
        """按更新时间倒序列出当前用户会话。"""
        uid = get_user_id()
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.title, s.scene, s.created_at, s.updated_at,
                       COUNT(m.id) AS message_count
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id AND m.user_id = s.user_id
                WHERE s.user_id = ?
                GROUP BY s.id
                ORDER BY s.updated_at DESC
                LIMIT ?
                """,
                (uid, limit),
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
        uid = get_user_id()
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT s.id, s.title, s.scene, s.created_at, s.updated_at,
                       COUNT(m.id) AS message_count
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id AND m.user_id = s.user_id
                WHERE s.id = ? AND s.user_id = ?
                GROUP BY s.id
                """,
                (session_id, uid),
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
        uid = get_user_id()
        cleaned = scene.strip()
        with _connect() as conn:
            conn.execute(
                "UPDATE sessions SET scene=? WHERE id=? AND user_id=?",
                (cleaned, session_id, uid),
            )

    def update_session_title(self, session_id: str, title: str) -> None:
        uid = get_user_id()
        cleaned = title.strip() or "新会话"
        with _connect() as conn:
            conn.execute(
                "UPDATE sessions SET title=? WHERE id=? AND user_id=?",
                (cleaned, session_id, uid),
            )

    def delete_session(self, session_id: str) -> None:
        uid = get_user_id()
        with _connect() as conn:
            conn.execute("DELETE FROM messages WHERE session_id=? AND user_id=?", (session_id, uid))
            conn.execute("DELETE FROM sessions WHERE id=? AND user_id=?", (session_id, uid))

    def list_messages(self, session_id: str) -> list[ChatMessage]:
        uid = get_user_id()
        with _connect() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM messages WHERE session_id=? AND user_id=? ORDER BY id",
                (session_id, uid),
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
        uid = get_user_id()
        now = _now()
        with _connect() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at, user_id) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, now, uid),
            )
            conn.execute(
                "UPDATE sessions SET updated_at=? WHERE id=? AND user_id=?",
                (now, session_id, uid),
            )

    def clear_messages(self, session_id: str) -> None:
        uid = get_user_id()
        with _connect() as conn:
            conn.execute("DELETE FROM messages WHERE session_id=? AND user_id=?", (session_id, uid))
