"""PostgreSQL 后端 —— SQLAlchemy 池化连接 + 统一查询接口。

Repository 层通过 DbConnection.execute() 调用，
传入 ? 占位符 SQL，本后端通过 exec_driver_sql 直通 psycopg。
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from sqlalchemy.sql.expression import Executable

from vnpy_common.storage.compat import DbRow
from vnpy_common.storage.config import APP_SEARCH_PATH
from vnpy_common.storage.dialect import split_sql_script, to_positional_sql
from vnpy_common.storage.pool import get_connection

CACHE_SEARCH_PATH = "cache, app, chat, auth, system, public"


class PostgresBackend:
    """持有池化 SQLAlchemy Connection；close() 归还到池。"""

    def __init__(self, url: str, *, search_path: str = APP_SEARCH_PATH) -> None:
        self._conn = get_connection(url)
        self._search_path = search_path
        self._closed = False
        self.last_rowcount = 0
        self._set_search_path(search_path)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def execute(
        self,
        sql: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> tuple[list[DbRow], int | None]:
        self._check_not_closed()
        pg_sql = to_positional_sql(sql)
        # SQLAlchemy exec_driver_sql 严格要求 tuple/dict，不接受 list
        coerced = tuple(params) if isinstance(params, list) else params
        result = self._conn.exec_driver_sql(pg_sql, coerced)
        self.last_rowcount = int(result.rowcount)
        if not result.returns_rows:
            return [], None
        raw_rows = result.fetchall()
        rows = [DbRow(dict(row._mapping)) for row in raw_rows]
        lastrowid: int | None = None
        if hasattr(result, "lastrowid"):
            try:
                lastrowid = int(result.lastrowid)
            except (TypeError, ValueError):
                lastrowid = None
        return rows, lastrowid

    def execute_stmt(
        self,
        statement: Executable,
    ) -> tuple[list[DbRow], int | None]:
        """执行 SQLAlchemy Core 语句（select / insert / update / delete）。"""
        self._check_not_closed()
        result = self._conn.execute(statement)
        self.last_rowcount = int(result.rowcount)
        if not result.returns_rows:
            return [], None
        raw_rows = result.fetchall()
        rows = [DbRow(dict(row._mapping)) for row in raw_rows]
        return rows, None

    def executemany(
        self,
        sql: str,
        params_seq: Sequence[Sequence[Any]],
    ) -> None:
        """批量执行 —— 复用底层 psycopg cursor 以支持真正的 executemany。"""
        self._check_not_closed()
        pg_sql = to_positional_sql(sql)
        # SQLAlchemy 的 exec_driver_sql 不支持 executemany 语义；
        # 通过底层 psycopg.Connection 直接操作。
        raw_conn = self._conn.connection  # psycopg.Connection
        with raw_conn.cursor() as cur:
            cur.execute(f"SET search_path TO {self._search_path}")
            cur.executemany(pg_sql, params_seq)
            self.last_rowcount = int(cur.rowcount)

    def executescript(self, script: str) -> None:
        self._check_not_closed()
        for statement in split_sql_script(script):
            pg_sql = to_positional_sql(statement)
            self._conn.exec_driver_sql(pg_sql)

    # ------------------------------------------------------------------
    # 事务
    # ------------------------------------------------------------------

    def commit(self) -> None:
        self._check_not_closed()
        self._conn.commit()

    def rollback(self) -> None:
        self._check_not_closed()
        self._conn.rollback()

    @contextmanager
    def transaction(self) -> Iterator[PostgresBackend]:
        """显式事务块 —— 自动提交/回滚。"""
        self._check_not_closed()
        trans = self._conn.begin()
        try:
            yield self
            trans.commit()
        except Exception:
            trans.rollback()
            raise

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def close(self) -> None:
        """归还连接到池。"""
        if self._closed:
            return
        self._closed = True
        try:
            self._conn.rollback()
        except Exception:
            pass
        self._conn.close()  # SQLAlchemy 连接 close() = 归还到池

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _check_not_closed(self) -> None:
        if self._closed:
            raise RuntimeError("PostgresBackend 已关闭")

    def _set_search_path(self, search_path: str) -> None:
        self._conn.exec_driver_sql(f"SET search_path TO {search_path}")

    @staticmethod
    def run_statements(conn: Any, statements: Sequence[str]) -> None:
        for stmt in statements:
            conn.exec_driver_sql(stmt)
