"""zak 业务库连接（PostgreSQL app schema）。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from vnpy_common.storage.session import connect_app
from vnpy_common.storage.tables import meta


@contextmanager
def connect() -> Iterator:
    with connect_app() as conn:
        yield conn


def _set_meta(conn, key: str, value: str) -> None:
    stmt = pg_insert(meta).values(key=key, value=value)
    stmt = stmt.on_conflict_do_update(
        index_elements=[meta.c.key],
        set_={"value": stmt.excluded.value},
    )
    conn.execute_stmt(stmt)


def _get_meta(conn, key: str) -> str | None:
    stmt = select(meta.c.value).where(meta.c.key == key)
    row = conn.execute_stmt(stmt).fetchone()
    return row["value"] if row else None


def get_meta(key: str) -> str | None:
    with connect() as conn:
        return _get_meta(conn, key)


def set_meta(key: str, value: str) -> None:
    with connect() as conn:
        _set_meta(conn, key, value)


def delete_meta(key: str) -> None:
    with connect() as conn:
        conn.execute_stmt(delete(meta).where(meta.c.key == key))
