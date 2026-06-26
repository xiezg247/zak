"""用户账号 DB 操作（委托 UsersRepository）。"""

from __future__ import annotations

from vnpy_ashare.storage.repositories.users import (
    UsersRepository,
    authenticate,
    create_user,
    list_users,
)
from vnpy_common.auth.users import DEFAULT_USERNAME, UserRecord
from vnpy_common.storage.config import require_database_url

_cached_default_user_id: str | None = None
_cached_default_user_db: str | None = None

_users_repo = UsersRepository()


def _invalidate_default_user_cache() -> None:
    global _cached_default_user_id, _cached_default_user_db
    _cached_default_user_id = None
    _cached_default_user_db = None


def users_table() -> str:
    return "auth.users"


def get_or_create_default_user_id() -> str:
    global _cached_default_user_id, _cached_default_user_db
    db_key = require_database_url()
    if _cached_default_user_id and _cached_default_user_db == db_key:
        return _cached_default_user_id
    user = _users_repo.get_or_create_default(default_username=DEFAULT_USERNAME)
    _cached_default_user_id = user.id
    _cached_default_user_db = db_key
    return user.id


def list_active_users() -> list[UserRecord]:
    return list_users()


def login(username: str, password: str) -> UserRecord | None:
    return authenticate(username=username, password=password)


__all__ = (
    "DEFAULT_USERNAME",
    "UserRecord",
    "_invalidate_default_user_cache",
    "authenticate",
    "create_user",
    "get_or_create_default_user_id",
    "list_active_users",
    "list_users",
    "login",
    "users_table",
)
