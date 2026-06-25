"""仅保留 default 用户，删除其余账号及其私有数据。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_common.auth.users import DEFAULT_USERNAME

from vnpy_ashare.storage.auth.migrate import PRIVATE_TABLES
from vnpy_ashare.storage.auth.users import (
    _invalidate_default_user_cache,
    create_user,
    ensure_users_schema,
    get_or_create_default_user_id,
    users_table,
)

_CHAT_USER_TABLES: tuple[str, ...] = (
    "messages",
    "llm_turn_traces",
    "llm_tool_calls",
    "sessions",
)

_APP_USER_TABLES: tuple[str, ...] = (*PRIVATE_TABLES, "feed_item_reads")


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


def _list_non_default_users(conn) -> list[tuple[str, str]]:
    table = users_table()
    rows = conn.execute(
        f"SELECT id, username FROM {table} WHERE username != ?",
        (DEFAULT_USERNAME,),
    ).fetchall()
    return [(str(row["id"]), str(row["username"])) for row in rows]


def _delete_user_scoped_rows(conn, *, table: str, user_ids: list[str], schema: str) -> None:
    if not user_ids:
        return
    qualified = f"{schema}.{table}"
    placeholders = ", ".join("?" for _ in user_ids)
    conn.execute(
        f"DELETE FROM {qualified} WHERE user_id IN ({placeholders})",
        tuple(user_ids),
    )


def _prune_user_data(conn, user_ids: list[str], tables: tuple[str, ...], schema: str) -> None:
    for table in tables:
        _delete_user_scoped_rows(conn, table=table, user_ids=user_ids, schema=schema)


def _ensure_default_user(conn) -> str:
    table = users_table()
    row = conn.execute(
        f"SELECT id FROM {table} WHERE username = ?",
        (DEFAULT_USERNAME,),
    ).fetchone()
    if row is not None:
        return str(row["id"])
    user = create_user(conn, username=DEFAULT_USERNAME, password="default", display_name="默认用户")
    return user.id


def prune_to_default_user() -> PruneUsersReport:
    """删除 default 以外所有用户及其 app/chat/auth 私有数据。"""
    from vnpy_ashare.storage.connection import connect, init_app_db
    from vnpy_common.storage.session import chat_session

    init_app_db()
    _invalidate_default_user_cache()

    other_ids: list[str] = []
    other_names: list[str] = []
    default_id = ""

    with connect() as conn:
        with conn.transaction():
            ensure_users_schema(conn)
            default_id = _ensure_default_user(conn)
            others = _list_non_default_users(conn)
            other_ids = [user_id for user_id, _ in others]
            other_names = [username for _, username in others]

            if other_ids:
                _prune_user_data(conn, other_ids, _APP_USER_TABLES, "app")
                _delete_user_scoped_rows(conn, table="user_preferences", user_ids=other_ids, schema="auth")
                table = users_table()
                placeholders = ", ".join("?" for _ in other_ids)
                conn.execute(
                    f"DELETE FROM {table} WHERE id IN ({placeholders})",
                    tuple(other_ids),
                )

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
