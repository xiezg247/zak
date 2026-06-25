"""Repository 基类（SQLAlchemy Core）。"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Table, delete, func, insert, select, update
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Select

from vnpy_common.storage.compat import DbConnection, DbCursor, DbRow
from vnpy_common.storage.session import connect_app


class BaseRepository:
    """表级 CRUD 基类；子类声明 ``table``。"""

    table: Table

    def prepare(self) -> None:
        """每次开连接前调用（如 init_app_db）。"""

    @contextmanager
    def session(self) -> Iterator[DbConnection]:
        self.prepare()
        with connect_app() as conn:
            yield conn

    def execute(self, statement) -> DbCursor:
        with self.session() as conn:
            return conn.execute_stmt(statement)

    def fetchall(self, statement) -> list[DbRow]:
        with self.session() as conn:
            return conn.execute_stmt(statement).fetchall()

    def fetchone(self, statement) -> DbRow | None:
        with self.session() as conn:
            return conn.execute_stmt(statement).fetchone()

    def run(self, callback: Callable[[DbConnection], Any]) -> Any:
        with self.session() as conn:
            return callback(conn)

    def count_where(self, *where: ColumnElement[bool]) -> int:
        stmt = select(func.count()).select_from(self.table)
        if where:
            stmt = stmt.where(*where)
        row = self.fetchone(stmt)
        return int(row[0]) if row is not None else 0

    def exists_where(self, *where: ColumnElement[bool]) -> bool:
        stmt = select(1).select_from(self.table).where(*where).limit(1)
        return self.fetchone(stmt) is not None

    def insert_values(self, conn: DbConnection, **values: Any) -> None:
        conn.execute_stmt(insert(self.table).values(**values))

    def insert_one(self, **values: Any) -> None:
        with self.session() as conn:
            self.insert_values(conn, **values)

    def delete_where(self, conn: DbConnection, *where: ColumnElement[bool]) -> int:
        cursor = conn.execute_stmt(delete(self.table).where(*where))
        return int(cursor.rowcount)

    def delete_matching(self, *where: ColumnElement[bool]) -> int:
        with self.session() as conn:
            return self.delete_where(conn, *where)

    def update_where(
        self,
        conn: DbConnection,
        values: dict[str, Any],
        *where: ColumnElement[bool],
    ) -> int:
        cursor = conn.execute_stmt(update(self.table).where(*where).values(**values))
        return int(cursor.rowcount)

    def update_matching(self, values: dict[str, Any], *where: ColumnElement[bool]) -> int:
        with self.session() as conn:
            return self.update_where(conn, values, *where)

    def select_columns(
        self,
        *columns,
        where: Sequence[ColumnElement[bool]] = (),
        order_by: Sequence[ColumnElement[Any]] = (),
        limit: int | None = None,
    ) -> Select[Any]:
        stmt = select(*columns).select_from(self.table)
        if where:
            stmt = stmt.where(*where)
        if order_by:
            stmt = stmt.order_by(*order_by)
        if limit is not None:
            stmt = stmt.limit(limit)
        return stmt
