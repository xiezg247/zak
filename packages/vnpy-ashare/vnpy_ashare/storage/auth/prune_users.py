"""仅保留 default 用户，删除其余账号及其私有数据。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_ashare.storage.auth.private_tables import PRIVATE_TABLES
from vnpy_ashare.storage.auth.users import (
    _invalidate_default_user_cache,
    get_or_create_default_user_id,
)
from vnpy_ashare.storage.repositories.user_preferences import UserPreferencesRepository
from vnpy_ashare.storage.repositories.users import UsersRepository
from vnpy_common.auth.users import DEFAULT_USERNAME

_CHAT_USER_TABLES: tuple[str, ...] = (
    "messages",
    "llm_turn_traces",
    "llm_tool_calls",
    "sessions",
)

_APP_USER_TABLES: tuple[str, ...] = (*PRIVATE_TABLES, "feed_item_reads")

_users_repo = UsersRepository()
_prefs_repo = UserPreferencesRepository()


@dataclass(frozen=True)
class PruneUsersReport:
    default_user_id: str
    removed_usernames: tuple[str, ...]
    removed_user_ids: tuple[str, ...]

    def summary_lines(self) -> list[str]:
        lines = [f"保留用户：{DEFAULT_USERNAME} ({self.default_user_id})"]
        if not self.removed_usernames:
            lines.append("无多余用户")
            return lines
        lines.append(f"已删除 {len(self.removed_usernames)} 个用户：{', '.join(self.removed_usernames)}")
        return lines


def _delete_user_scoped_rows(conn, *, table: str, user_ids: list[str], schema: str) -> None:
    if not user_ids:
        return
    qualified = f"{schema}.{table}"
    placeholders = ", ".join("%s" for _ in user_ids)
    conn.execute(
        f"DELETE FROM {qualified} WHERE user_id IN ({placeholders})",
        tuple(user_ids),
    )


def _prune_user_data(conn, user_ids: list[str], tables: tuple[str, ...], schema: str) -> None:
    for table in tables:
        _delete_user_scoped_rows(conn, table=table, user_ids=user_ids, schema=schema)


def prune_to_default_user() -> PruneUsersReport:
    """删除 default 以外所有用户及其 app/chat/auth 私有数据。"""
    from vnpy_common.storage.session import chat_session

    _invalidate_default_user_cache()

    other_ids: list[str] = []
    other_names: list[str] = []
    default_id = ""

    with _users_repo.transaction() as conn:
        default_id = _users_repo.ensure_default_conn(conn, default_username=DEFAULT_USERNAME)
        others = _users_repo.list_non_default_conn(conn, default_username=DEFAULT_USERNAME)
        other_ids = [user_id for user_id, _ in others]
        other_names = [username for _, username in others]

        if other_ids:
            _prune_user_data(conn, other_ids, _APP_USER_TABLES, "app")
            _prefs_repo.delete_for_user_ids(conn, other_ids)
            _users_repo.delete_ids(conn, other_ids)

    if other_ids:
        with chat_session() as chat_conn:
            _prune_user_data(chat_conn, other_ids, _CHAT_USER_TABLES, "chat")

    _invalidate_default_user_cache()
    resolved_default = get_or_create_default_user_id()

    return PruneUsersReport(
        default_user_id=resolved_default or default_id,
        removed_usernames=tuple(other_names),
        removed_user_ids=tuple(other_ids),
    )
