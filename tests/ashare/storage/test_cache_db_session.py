"""缓存会话测试（PostgreSQL cache schema）。"""

from __future__ import annotations

from vnpy_ashare.storage.cache.db_session import cache_db_session


def test_cache_session_roundtrip(pg_storage) -> None:
    _ = pg_storage
    schema = """
    CREATE TABLE IF NOT EXISTS _cache_session_smoke (
        id SERIAL PRIMARY KEY,
        value TEXT NOT NULL
    );
    """
    with cache_db_session(schema) as conn:
        conn.execute("INSERT INTO _cache_session_smoke (value) VALUES (?)", ("ok",))
    with cache_db_session(schema) as conn:
        row = conn.execute("SELECT value FROM _cache_session_smoke ORDER BY id DESC LIMIT 1").fetchone()
    assert row is not None
    assert row["value"] == "ok"
