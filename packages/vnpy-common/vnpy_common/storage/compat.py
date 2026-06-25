"""PostgreSQL 连接兼容层（DbConnection / DbRow）。"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from sqlalchemy.sql.expression import Executable


class DbRow(dict[str, Any]):
    """兼容 dict-row 的下标访问。"""

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class DbCursor:
    def __init__(
        self,
        rows: list[DbRow] | None = None,
        *,
        lastrowid: int | None = None,
        rowcount: int = 0,
    ) -> None:
        self._rows = rows or []
        self._index = 0
        self.lastrowid = lastrowid
        self.rowcount = rowcount

    def fetchone(self) -> DbRow | None:
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def fetchall(self) -> list[DbRow]:
        rest = self._rows[self._index :]
        self._index = len(self._rows)
        return rest


class DbConnection:
    """统一 execute / executescript / commit 接口。"""

    def __init__(self, backend: Any) -> None:
        self._backend = backend

    def execute(
        self,
        sql: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> DbCursor:
        rows, lastrowid = self._backend.execute(sql, params)
        rowcount = self._backend.last_rowcount
        return DbCursor(rows, lastrowid=lastrowid, rowcount=rowcount)

    def execute_stmt(self, statement: Executable) -> DbCursor:
        """执行 SQLAlchemy Core 语句。"""
        rows, lastrowid = self._backend.execute_stmt(statement)
        rowcount = self._backend.last_rowcount
        return DbCursor(rows, lastrowid=lastrowid, rowcount=rowcount)

    def executemany(
        self,
        sql: str,
        params_seq: Sequence[Sequence[Any]],
    ) -> None:
        self._backend.executemany(sql, params_seq)

    def executescript(self, script: str) -> None:
        self._backend.executescript(script)

    def commit(self) -> None:
        self._backend.commit()

    def rollback(self) -> None:
        self._backend.rollback()

    @contextmanager
    def transaction(self) -> Iterator[DbConnection]:
        """多语句原子写（autocommit 连接上显式事务）。"""
        with self._backend.transaction():
            yield self

    def close(self) -> None:
        self._backend.close()
