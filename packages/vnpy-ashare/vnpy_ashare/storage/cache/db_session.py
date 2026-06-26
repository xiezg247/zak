"""缓存 / 扩展表连接会话（PostgreSQL cache / app schema）。"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from vnpy_ashare.storage.connection import connect
from vnpy_common.storage.session import cache_session

_schema_applied: set[str] = set()


@contextmanager
def cache_db_session(
    schema: str,
    *,
    prepare: Callable[[], None] | None = None,
) -> Iterator:
    """打开 cache schema 表会话（同进程内相同 DDL 只执行一次）。"""
    schema_key = schema.strip()
    ddl = schema_key if schema_key and schema_key not in _schema_applied else ""
    with cache_session("", ddl, prepare=prepare) as conn:
        if ddl:
            _schema_applied.add(schema_key)
        yield conn


@contextmanager
def app_db_session(schema: str) -> Iterator:
    """app schema 扩展表会话。"""
    with connect() as conn:
        if schema.strip():
            conn.executescript(schema)
        yield conn
