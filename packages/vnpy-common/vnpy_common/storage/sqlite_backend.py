"""SQLite 后端。"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from vnpy_common.storage.compat import DbRow
from vnpy_common.storage.dialect import split_sql_script


class SqliteBackend:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self.last_rowcount = 0

    def execute(
        self,
        sql: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> tuple[list[DbRow], int | None]:
        if params is None:
            cursor = self._conn.execute(sql)
        else:
            cursor = self._conn.execute(sql, params)
        self.last_rowcount = int(cursor.rowcount)
        lastrowid = int(cursor.lastrowid) if cursor.lastrowid is not None else None
        if cursor.description is None:
            return [], lastrowid
        return [DbRow(dict(row)) for row in cursor.fetchall()], lastrowid

    def executemany(
        self,
        sql: str,
        params_seq: Sequence[Sequence[Any]],
    ) -> None:
        self._conn.executemany(sql, params_seq)
        self.last_rowcount = int(self._conn.total_changes)

    def executescript(self, script: str) -> None:
        self._conn.executescript(script)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {str(row[1]) for row in rows}

    @staticmethod
    def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = SqliteBackend.table_columns(conn, table)
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")

    @staticmethod
    def run_script(conn: sqlite3.Connection, script: str) -> None:
        conn.executescript(script)

    @staticmethod
    def split_script(script: str) -> list[str]:
        return split_sql_script(script)
