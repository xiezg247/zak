"""SQLite 缓存会话测试。"""

from __future__ import annotations

from vnpy_ashare.storage.cache.sqlite_session import sqlite_cache_session


def test_sqlite_cache_session_creates_table(tmp_path) -> None:
    db_path = tmp_path / "cache.db"
    schema = "CREATE TABLE IF NOT EXISTS demo (id INTEGER PRIMARY KEY, value TEXT NOT NULL);"
    with sqlite_cache_session(db_path, schema) as conn:
        conn.execute("INSERT INTO demo (value) VALUES (?)", ("ok",))
    with sqlite_cache_session(db_path, schema) as conn:
        row = conn.execute("SELECT value FROM demo").fetchone()
    assert row is not None
    assert row["value"] == "ok"
