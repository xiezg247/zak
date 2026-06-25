"""zak 业务库连接（PostgreSQL app schema）。"""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path

from vnpy_common.paths import legacy_app_db_path
from vnpy_common.storage.session import connect_app


@contextmanager
def connect() -> Iterator:
    with connect_app() as conn:
        yield conn


def init_app_db() -> Path:
    """应用库路径标记（不自动 migrate；请先 uv run python cli.py db upgrade）。"""
    return legacy_app_db_path()


def _set_meta(conn, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _get_meta(conn, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def get_meta(key: str) -> str | None:
    init_app_db()
    with connect() as conn:
        return _get_meta(conn, key)


def set_meta(key: str, value: str) -> None:
    init_app_db()
    with connect() as conn:
        _set_meta(conn, key, value)
