"""auth.users repository。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, insert, select

from vnpy_common.storage.repository import BaseRepository
from vnpy_common.auth.users import DEFAULT_USERNAME, UserRecord, hash_password, verify_password
from vnpy_common.storage.compat import DbConnection
from vnpy_common.storage.tables.auth import users as auth_users


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class UsersRepository(BaseRepository):
    table = auth_users

    def _insert_user(
        self,
        conn: DbConnection,
        *,
        user_id: str,
        username: str,
        password: str,
        display_name: str,
    ) -> UserRecord:
        name = username.strip()
        now = _now_iso()
        record = UserRecord(id=user_id, username=name, display_name=display_name.strip() or name)
        conn.execute_stmt(
            insert(auth_users).values(
                id=user_id,
                username=name,
                display_name=record.display_name,
                password_hash=hash_password(password),
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        return record

    def create(
        self,
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
        record = UserRecord(id=user_id, username=name, display_name=display_name.strip() or name)

        def _write(conn: DbConnection) -> None:
            self._insert_user(
                conn,
                user_id=user_id,
                username=name,
                password=password,
                display_name=record.display_name,
            )

        self.run(_write)
        return record

    def authenticate(self, *, username: str, password: str) -> UserRecord | None:
        name = username.strip()
        row = self.fetchone(
            select(
                auth_users.c.id,
                auth_users.c.username,
                auth_users.c.display_name,
                auth_users.c.password_hash,
            ).where(
                auth_users.c.username == name,
                auth_users.c.is_active.is_(True),
            )
        )
        if row is None:
            return None
        if not verify_password(password, str(row["password_hash"])):
            return None
        return UserRecord(
            id=str(row["id"]),
            username=str(row["username"]),
            display_name=str(row["display_name"] or ""),
        )

    def list_active(self) -> list[UserRecord]:
        rows = self.fetchall(
            select(auth_users.c.id, auth_users.c.username, auth_users.c.display_name)
            .where(auth_users.c.is_active.is_(True))
            .order_by(auth_users.c.username)
        )
        return [
            UserRecord(id=str(r["id"]), username=str(r["username"]), display_name=str(r["display_name"] or ""))
            for r in rows
        ]

    def get_id_by_username(self, username: str) -> str | None:
        row = self.fetchone(
            select(auth_users.c.id).where(
                auth_users.c.username == username.strip(),
                auth_users.c.is_active.is_(True),
            )
        )
        return str(row["id"]) if row else None

    def get_id_by_username_conn(self, conn: DbConnection, username: str) -> str | None:
        row = conn.execute_stmt(
            select(auth_users.c.id).where(
                auth_users.c.username == username.strip(),
                auth_users.c.is_active.is_(True),
            )
        ).fetchone()
        return str(row["id"]) if row else None

    def list_non_default(self, *, default_username: str = DEFAULT_USERNAME) -> list[tuple[str, str]]:
        rows = self.fetchall(
            select(auth_users.c.id, auth_users.c.username).where(auth_users.c.username != default_username)
        )
        return [(str(row["id"]), str(row["username"])) for row in rows]

    def list_non_default_conn(self, conn: DbConnection, *, default_username: str = DEFAULT_USERNAME) -> list[tuple[str, str]]:
        rows = conn.execute_stmt(
            select(auth_users.c.id, auth_users.c.username).where(auth_users.c.username != default_username)
        ).fetchall()
        return [(str(row["id"]), str(row["username"])) for row in rows]

    def delete_ids(self, conn: DbConnection, user_ids: list[str]) -> None:
        if not user_ids:
            return
        conn.execute_stmt(delete(auth_users).where(auth_users.c.id.in_(user_ids)))

    def ensure_default_conn(self, conn: DbConnection, *, default_username: str = DEFAULT_USERNAME) -> str:
        existing_id = self.get_id_by_username_conn(conn, default_username)
        if existing_id is not None:
            return existing_id
        try:
            user = self._insert_user(
                conn,
                user_id=uuid.uuid4().hex,
                username=default_username,
                password="default",
                display_name="默认用户",
            )
            return user.id
        except Exception as exc:
            if not _is_unique_violation(exc):
                raise
            existing_id = self.get_id_by_username_conn(conn, default_username)
            if existing_id is None:
                raise
            return existing_id

    def get_or_create_default(self, *, default_username: str = DEFAULT_USERNAME) -> UserRecord:
        existing_id = self.get_id_by_username(default_username)
        if existing_id is not None:
            row = self.fetchone(
                select(auth_users.c.id, auth_users.c.username, auth_users.c.display_name).where(
                    auth_users.c.id == existing_id
                )
            )
            assert row is not None
            return UserRecord(
                id=str(row["id"]),
                username=str(row["username"]),
                display_name=str(row["display_name"] or ""),
            )
        try:
            return self.create(username=default_username, password="default", display_name="默认用户")
        except Exception as exc:
            if not _is_unique_violation(exc):
                raise
            existing_id = self.get_id_by_username(default_username)
            if existing_id is None:
                raise
            return UserRecord(id=existing_id, username=default_username, display_name="默认用户")


def _is_unique_violation(exc: BaseException) -> bool:
    try:
        import psycopg

        return isinstance(exc, psycopg.errors.UniqueViolation)
    except ImportError:
        return False


_users_repo = UsersRepository()

create_user = _users_repo.create
list_users = _users_repo.list_active
authenticate = _users_repo.authenticate
