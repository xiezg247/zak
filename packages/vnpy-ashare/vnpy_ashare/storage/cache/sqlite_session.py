"""SQLite 磁盘缓存公共连接会话。"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def sqlite_cache_session(
    db_path: Path,
    schema: str,
    *,
    prepare: Callable[[], None] | None = None,
) -> Iterator[sqlite3.Connection]:
    """打开缓存库、执行 schema 并在退出时 commit/rollback。"""
    if prepare is not None:
        prepare()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if schema.strip():
            conn.executescript(schema)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
