"""应用 / 缓存 / 对话库连接入口（PostgreSQL 池化连接）。"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from vnpy_common.storage.compat import DbConnection
from vnpy_common.storage.config import APP_SEARCH_PATH, require_database_url
from vnpy_common.storage.postgres_backend import CACHE_SEARCH_PATH, PostgresBackend


def _open_backend(*, search_path: str) -> DbConnection:
    return DbConnection(PostgresBackend(require_database_url(), search_path=search_path))


def _close_connection(conn: DbConnection) -> None:
    try:
        conn.close()
    except Exception:
        pass


@contextmanager
def connect_app() -> Iterator[DbConnection]:
    """应用库会话（app schema 优先）。"""
    conn = _open_backend(search_path=APP_SEARCH_PATH)
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        _close_connection(conn)


@contextmanager
def chat_session() -> Iterator[DbConnection]:
    """对话库会话（app schema）。"""
    conn = _open_backend(search_path=APP_SEARCH_PATH)
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        _close_connection(conn)


@contextmanager
def cache_session(
    cache_file: str,
    schema: str,
    *,
    prepare: Callable[[], None] | None = None,
) -> Iterator[DbConnection]:
    """磁盘缓存会话（cache schema）。"""
    _ = cache_file
    if prepare is not None:
        prepare()
    conn = _open_backend(search_path=CACHE_SEARCH_PATH)
    try:
        if schema.strip():
            conn.executescript(schema)
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        _close_connection(conn)


_migration_done = False


def ensure_postgres_migrated() -> None:
    """显式执行 Alembic upgrade head（启动时不自动调用；请优先用 cli db upgrade）。"""
    global _migration_done
    if _migration_done:
        return
    from vnpy_common.storage.migrate import upgrade_head

    upgrade_head()
    _migration_done = True
