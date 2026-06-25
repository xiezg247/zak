"""PostgreSQL bulk upsert 辅助。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql.elements import ColumnElement

from vnpy_common.storage.compat import DbConnection


def bulk_upsert(
    conn: DbConnection,
    table: Table,
    values: Sequence[Mapping[str, Any]],
    *,
    conflict_columns: Sequence[str | ColumnElement[Any]],
    update_columns: Sequence[str],
) -> None:
    """INSERT … ON CONFLICT DO UPDATE（批量）。"""
    if not values:
        return
    index_elements = [
        table.c[column] if isinstance(column, str) else column for column in conflict_columns
    ]
    stmt = pg_insert(table).values(list(values))
    excluded = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        index_elements=index_elements,
        set_={column: excluded[column] for column in update_columns},
    )
    conn.execute_stmt(stmt)


def insert_ignore(
    conn: DbConnection,
    table: Table,
    values: Mapping[str, Any],
) -> None:
    """INSERT … ON CONFLICT DO NOTHING。"""
    stmt = pg_insert(table).values(dict(values)).on_conflict_do_nothing()
    conn.execute_stmt(stmt)
