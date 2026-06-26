"""用户账号 DB 操作。"""

from __future__ import annotations

import uuid
from datetime import datetime

from vnpy_common.auth.users import DEFAULT_USERNAME, UserRecord, hash_password, verify_password

_cached_default_user_id: str | None = None
_cached_default_user_db: str | None = None


def _invalidate_default_user_cache() -> None:
    global _cached_default_user_id, _cached_default_user_db
    _cached_default_user_id = None
    _cached_default_user_db = None


def users_table() -> str:
    return "auth.users"


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def create_user(
    conn,
    *,
    username: str,
    password: str,
    display_name: str = "",
) -> UserRecord:
    name = username.strip()
    if not name:
        raise ValueError("用户名不能为空")
    if not password:
        raise ValueError("密码不能为空")
    user_id = uuid.uuid4().hex
    now = _now_iso()
    table = users_table()
    conn.execute(
        f"""
        INSERT INTO {table} (id, username, display_name, password_hash, is_active, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            user_id,
            name,
            display_name.strip() or name,
            hash_password(password),
            True,
            now,
            now,
        ),
    )
    return UserRecord(id=user_id, username=name, display_name=display_name.strip() or name)


def authenticate(conn, *, username: str, password: str) -> UserRecord | None:
    name = username.strip()
    table = users_table()
    row = conn.execute(
        f"SELECT id, username, display_name, password_hash FROM {table} WHERE username = %s AND is_active = true",
        (name,),
    ).fetchone()
    if row is None:
        return None
    if not verify_password(password, str(row["password_hash"])):
        return None
    return UserRecord(id=str(row["id"]), username=str(row["username"]), display_name=str(row["display_name"] or ""))


def list_users(conn) -> list[UserRecord]:
    table = users_table()
    rows = conn.execute(
        f"SELECT id, username, display_name FROM {table} WHERE is_active = true ORDER BY username",
    ).fetchall()
    return [UserRecord(id=str(r["id"]), username=str(r["username"]), display_name=str(r["display_name"] or "")) for r in rows]


def get_or_create_default_user_id() -> str:
    global _cached_default_user_id, _cached_default_user_db
    from vnpy_common.storage.config import require_database_url

    db_key = require_database_url()
    if _cached_default_user_id and _cached_default_user_db == db_key:
        return _cached_default_user_id
    from vnpy_ashare.storage.connection import connect

    with connect() as conn:
        table = users_table()
        row = conn.execute(
            f"SELECT id FROM {table} WHERE username = %s",
            (DEFAULT_USERNAME,),
        ).fetchone()
        if row is not None:
            _cached_default_user_id = str(row["id"])
            _cached_default_user_db = db_key
            return _cached_default_user_id
        try:
            user = create_user(conn, username=DEFAULT_USERNAME, password="default", display_name="默认用户")
        except Exception as exc:
            if not _is_unique_violation(exc):
                raise
            row = conn.execute(
                f"SELECT id FROM {table} WHERE username = %s",
                (DEFAULT_USERNAME,),
            ).fetchone()
            if row is None:
                raise
            user = UserRecord(id=str(row["id"]), username=DEFAULT_USERNAME, display_name="默认用户")
        _cached_default_user_id = user.id
        _cached_default_user_db = db_key
        return user.id


def _is_unique_violation(exc: BaseException) -> bool:
    try:
        import psycopg

        return isinstance(exc, psycopg.errors.UniqueViolation)
    except ImportError:
        return False


def list_active_users() -> list[UserRecord]:
    from vnpy_ashare.storage.connection import connect

    with connect() as conn:
        return list_users(conn)


def login(username: str, password: str) -> UserRecord | None:
    from vnpy_ashare.storage.connection import connect

    with connect() as conn:
        return authenticate(conn, username=username, password=password)
