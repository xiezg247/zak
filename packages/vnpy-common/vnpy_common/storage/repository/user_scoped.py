"""带 user_id 行级隔离的 Repository 基类。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, ClassVar

from sqlalchemy.sql.elements import ColumnElement

from vnpy_common.storage.compat import DbConnection, DbRow
from vnpy_common.storage.query import user_scope
from vnpy_common.storage.repository.base import BaseRepository


class UserScopedRepository(BaseRepository):
    """当前用户私有表：自动注入 ``user_id`` 过滤。"""

    user_id_resolver: ClassVar[Callable[[], str]]

    @property
    def user_id_col(self):
        return self.table.c.user_id

    def current_user_id(self) -> str:
        return type(self).user_id_resolver()

    def scope(self, *extras: ColumnElement[bool]) -> ColumnElement[bool]:
        return user_scope(self.user_id_col, self.current_user_id(), *extras)

    def count_for_user(self, *extras: ColumnElement[bool]) -> int:
        if extras:
            return self.count_where(self.scope(*extras))
        return self.count_where(self.scope())

    def exists_for_user(self, *extras: ColumnElement[bool]) -> bool:
        return self.exists_where(self.scope(*extras))

    def delete_for_user(self, conn: DbConnection, *extras: ColumnElement[bool]) -> int:
        return self.delete_where(conn, self.scope(*extras))

    def delete_all_for_user(self) -> int:
        with self.session() as conn:
            return self.delete_for_user(conn)

    def list_for_user(
        self,
        *columns,
        extras: Sequence[ColumnElement[bool]] = (),
        order_by: Sequence[ColumnElement[Any]] = (),
        limit: int | None = None,
    ) -> list[DbRow]:
        where = (self.scope(*extras),) if extras else (self.scope(),)
        stmt = self.select_columns(
            *columns,
            where=where,
            order_by=order_by,
            limit=limit,
        )
        return self.fetchall(stmt)

    def insert_for_user(self, conn: DbConnection, **values: Any) -> None:
        values = dict(values)
        values.setdefault("user_id", self.current_user_id())
        self.insert_values(conn, **values)

    def insert_one_for_user(self, **values: Any) -> None:
        with self.session() as conn:
            self.insert_for_user(conn, **values)
