"""会话 CRUD 与 floating / assistant 双轨绑定。"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import Field

from vnpy_llm.chat.session_surface import SessionSurfaceStore, Surface
from vnpy_common.domain.base import FrozenModel
from vnpy_llm.chat.store import ChatMessage, ChatSession, ChatStore

SessionNotify = Callable[["SessionNotification"], None]


class SessionNotification(FrozenModel):
    """会话变更通知（由 LlmEngine 转为 Qt 信号与 Trace 加载）。"""

    messages_changed: bool = Field(default=False, description="消息列表是否变更")
    sessions_changed: bool = Field(default=False, description="会话列表是否变更")
    trace_changed: bool = Field(default=False, description="Trace 是否变更")
    trace_session_loaded: str | None = Field(default=None, description="需加载 Trace 的会话 ID")
    trace_clear_session: str | None = Field(default=None, description="需清空 Trace 的会话 ID")


class SessionManager:
    """ChatStore + SessionSurfaceStore 的统一会话控制。"""

    def __init__(
        self,
        *,
        store: ChatStore | None = None,
        surface_store: SessionSurfaceStore | None = None,
        on_notify: SessionNotify | None = None,
    ) -> None:
        self.store = store or ChatStore()
        self._surface_store = surface_store or SessionSurfaceStore()
        self._on_notify = on_notify
        self._active_surface: Surface = "assistant"
        default_session_id = self.store.get_or_create_default_session()
        floating_id = self._ensure_session_exists(
            self._surface_store.get("floating", fallback=default_session_id),
        )
        assistant_id = self._ensure_session_exists(
            self._surface_store.get("assistant", fallback=default_session_id),
        )
        self._surface_store.set("floating", floating_id)
        self._surface_store.set("assistant", assistant_id)
        self.session_id: str = assistant_id

    @property
    def surface_store(self) -> SessionSurfaceStore:
        return self._surface_store

    @property
    def active_surface(self) -> Surface:
        return self._active_surface

    def _notify(self, note: SessionNotification) -> None:
        if self._on_notify is not None:
            self._on_notify(note)

    def _ensure_session_exists(self, session_id: str) -> str:
        if self.store.get_session(session_id) is not None:
            return session_id
        return self.store.get_or_create_default_session()

    def _bind_surface_session(self, surface: Surface, session_id: str) -> None:
        session_id = self._ensure_session_exists(session_id)
        self._surface_store.set(surface, session_id)

    def get_messages(self, session_id: str | None = None) -> list[ChatMessage]:
        sid = session_id or self.session_id
        return self.store.list_messages(sid)

    def list_sessions(self) -> list[ChatSession]:
        return self.store.list_sessions()

    def get_session(self, session_id: str | None = None) -> ChatSession | None:
        return self.store.get_session(session_id or self.session_id)

    def get_current_session_title(self) -> str:
        session = self.get_session()
        if session is None:
            return "会话"
        title = session.title.strip()
        return title or "会话"

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
            self._notify(
                SessionNotification(
                    messages_changed=True,
                    sessions_changed=True,
                    trace_changed=True,
                    trace_session_loaded=next_id,
                )
            )

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
            return self.new_session(surface=surface, scene=scene)
        if scene.strip():
            self._apply_session_scene(self.session_id, scene)
        return self.session_id

    def _apply_session_scene(self, session_id: str, scene: str) -> None:
        cleaned = scene.strip()
        if not cleaned:
            return
        self.store.update_session_scene(session_id, cleaned)
        self._notify(SessionNotification(sessions_changed=True))

    def switch_session(self, session_id: str) -> None:
        if session_id == self.session_id:
            return
        if self.store.get_session(session_id) is None:
            return
        self.session_id = session_id
        self._bind_surface_session(self._active_surface, session_id)
        self._notify(
            SessionNotification(
                messages_changed=True,
                sessions_changed=True,
                trace_changed=True,
                trace_session_loaded=session_id,
            )
        )

    def rename_session(self, session_id: str, title: str) -> None:
        self.store.update_session_title(session_id, title)
        self._notify(SessionNotification(sessions_changed=True))

    def delete_session(self, session_id: str) -> None:
        self._notify(SessionNotification(trace_clear_session=session_id))
        self.store.delete_session(session_id)
        remaining = self.store.list_sessions(limit=1)
        replacement = remaining[0].id if remaining else self.store.create_session()
        self._surface_store.clear_binding(session_id, replacement=replacement)
        if session_id == self.session_id:
            self.session_id = self._ensure_session_exists(
                self._surface_store.get(self._active_surface, fallback=replacement),
            )
            self._bind_surface_session(self._active_surface, self.session_id)
            self._notify(
                SessionNotification(
                    messages_changed=True,
                    trace_changed=True,
                    trace_session_loaded=self.session_id,
                )
            )
        self._notify(SessionNotification(sessions_changed=True))

    def clear_session(self, session_id: str | None = None) -> None:
        sid = session_id or self.session_id
        self._notify(SessionNotification(trace_clear_session=sid))
        self.store.clear_messages(sid)
        self._notify(
            SessionNotification(
                messages_changed=True,
                sessions_changed=True,
                trace_changed=True,
            )
        )

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
            self._notify(
                SessionNotification(
                    messages_changed=True,
                    trace_changed=True,
                    trace_session_loaded=session_id,
                )
            )
        self._notify(SessionNotification(sessions_changed=True))
        return session_id

    def maybe_update_session_title(self, session_id: str, user_text: str) -> None:
        session = self.store.get_session(session_id)
        if session is None or session.title not in ("新会话", "默认会话"):
            return
        title = user_text.replace("\n", " ").strip()[:30]
        if not title:
            return
        self.store.update_session_title(session_id, title)
        self._notify(SessionNotification(sessions_changed=True))

    def append_message(self, session_id: str, role: str, content: str) -> None:
        if role == "user":
            self.maybe_update_session_title(session_id, content)
        self.store.append_message(session_id, role=role, content=content)
        self._notify(SessionNotification(messages_changed=True, sessions_changed=True))

    def bind_active_surface_on_close(self) -> None:
        self._bind_surface_session(self._active_surface, self.session_id)
