"""当前登录用户 ContextVar。"""

from __future__ import annotations

from contextvars import ContextVar

_current_user_id: ContextVar[str | None] = ContextVar("zak_current_user_id", default=None)


def set_current_user(user_id: str) -> None:
    _current_user_id.set(user_id.strip())


def clear_current_user() -> None:
    _current_user_id.set(None)


def get_current_user_id() -> str | None:
    return _current_user_id.get()
