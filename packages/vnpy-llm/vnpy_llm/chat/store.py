"""AI 对话会话持久化（PostgreSQL chat schema）。"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import delete, func, insert, select, update

from vnpy_llm.domain.chat import ChatMessage, ChatSession
from vnpy_llm.storage.repository.chat import ChatUserScopedRepository
from vnpy_common.storage.tables.chat import chat_messages as cm
from vnpy_common.storage.tables.chat import chat_sessions as cs

MAX_MESSAGES_PER_SESSION = 50
MAX_TOOL_RESULT_CHARS = 2000


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _session_row_to_model(row) -> ChatSession:
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


class ChatRepository(ChatUserScopedRepository):
    table = cs

    def _sessions_with_counts_select(self):
        return (
            select(
                cs.c.id,
                cs.c.title,
                cs.c.scene,
                cs.c.created_at,
                cs.c.updated_at,
                func.count(cm.c.id).label("message_count"),
            )
            .select_from(cs)
            .outerjoin(cm, (cm.c.session_id == cs.c.id) & (cm.c.user_id == cs.c.user_id))
            .where(self.scope())
            .group_by(cs.c.id)
        )

    def get_or_create_default_session(self) -> str:
        """获取最近会话 id，无则创建「默认会话」。"""
        row = self.fetchone(
            select(cs.c.id).where(self.scope()).order_by(cs.c.updated_at.desc()).limit(1)
        )
        if row is not None:
            return str(row["id"])
        session_id = uuid.uuid4().hex
        now = _now()
        self.insert_one_for_user(id=session_id, title="默认会话", scene="", created_at=now, updated_at=now)
        return session_id

    def create_session(self, *, title: str = "新会话", scene: str = "") -> str:
        """创建新会话并返回 id。"""
        session_id = uuid.uuid4().hex
        now = _now()
        self.insert_one_for_user(
            id=session_id,
            title=title,
            scene=scene.strip(),
            created_at=now,
            updated_at=now,
        )
        return session_id

    def list_sessions(self, *, limit: int = 50) -> list[ChatSession]:
        """按更新时间倒序列出当前用户会话。"""
        stmt = self._sessions_with_counts_select().order_by(cs.c.updated_at.desc()).limit(limit)
        rows = self.fetchall(stmt)
        return [_session_row_to_model(row) for row in rows]

    def get_session(self, session_id: str) -> ChatSession | None:
        stmt = self._sessions_with_counts_select().where(self.scope(cs.c.id == session_id))
        row = self.fetchone(stmt)
        return _session_row_to_model(row) if row is not None else None

    def update_session_scene(self, session_id: str, scene: str) -> None:
        self.update_matching({"scene": scene.strip()}, self.scope(cs.c.id == session_id))

    def update_session_title(self, session_id: str, title: str) -> None:
        cleaned = title.strip() or "新会话"
        self.update_matching({"title": cleaned}, self.scope(cs.c.id == session_id))

    def delete_session(self, session_id: str) -> None:
        def _write(conn) -> None:
            conn.execute_stmt(delete(cm).where(self.scope_table(cm, cm.c.session_id == session_id)))
            self.delete_where(conn, self.scope(cs.c.id == session_id))

        self.run(_write)

    def list_messages(self, session_id: str) -> list[ChatMessage]:
        rows = self.fetchall(
            select(cm.c.role, cm.c.content, cm.c.created_at)
            .where(self.scope_table(cm, cm.c.session_id == session_id))
            .order_by(cm.c.id.asc())
        )
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

        def _write(conn) -> None:
            conn.execute_stmt(
                insert(cm).values(
                    session_id=session_id,
                    role=role,
                    content=content,
                    created_at=now,
                    user_id=self.current_user_id(),
                )
            )
            conn.execute_stmt(
                update(cs).where(self.scope(cs.c.id == session_id)).values(updated_at=now)
            )

        self.run(_write)

    def clear_messages(self, session_id: str) -> None:
        def _write(conn) -> None:
            conn.execute_stmt(
                delete(cm).where(self.scope_table(cm, cm.c.session_id == session_id))
            )

        self.run(_write)

_repo = ChatRepository()


@contextmanager
def _connect():
    with _repo.session() as conn:
        yield conn


class ChatStore(ChatRepository):
    """会话与消息的 CRUD；单会话最多保留 MAX_MESSAGES_PER_SESSION 条。"""
