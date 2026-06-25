"""A 股 app schema Repository 基类。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql.elements import ColumnElement

from vnpy_ashare.storage.auth.scope import get_user_id
from vnpy_ashare.storage.connection import init_app_db
from vnpy_common.storage.query import user_scope
from vnpy_common.storage.repository import BaseRepository, UserScopedRepository
from vnpy_common.storage.tables import meta


class AppBaseRepository(BaseRepository):
    """绑定 app 库 init。"""

    def prepare(self) -> None:
        init_app_db()


class AppUserScopedRepository(UserScopedRepository):
    """绑定 app 库 init + 当前 user_id 解析。"""

    @staticmethod
    def user_id_resolver() -> str:
        return get_user_id()

    def prepare(self) -> None:
        init_app_db()

    def scope_table(self, table, *extras: ColumnElement[bool]) -> ColumnElement[bool]:
        """对任意带 user_id 的表生成当前用户过滤。"""
        return user_scope(table.c.user_id, self.current_user_id(), *extras)


class MetaRepository(AppBaseRepository):
    table = meta

    def get_value(self, key: str) -> str | None:
        row = self.fetchone(select(meta.c.value).where(meta.c.key == key))
        return str(row["value"]) if row else None

    def upsert_value(self, key: str, value: str) -> None:
        def _write(conn) -> None:
            stmt = pg_insert(meta).values(key=key, value=value)
            stmt = stmt.on_conflict_do_update(
                index_elements=[meta.c.key],
                set_={"value": stmt.excluded.value},
            )
            conn.execute_stmt(stmt)

        self.run(_write)

    def delete_keys(self, *keys: str) -> None:
        if not keys:
            return
        self.delete_matching(meta.c.key.in_(keys))
