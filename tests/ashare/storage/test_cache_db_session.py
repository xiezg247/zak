"""缓存会话测试（PostgreSQL cache schema + Repository）。"""

from __future__ import annotations

from sqlalchemy import Column, MetaData, Table, Text, insert

from vnpy_ashare.storage.repository.cache import CacheBaseRepository
from vnpy_common.storage.tables.cache import metadata as cache_metadata


class _SmokeRepo(CacheBaseRepository):
    table = Table(
        "_cache_session_smoke",
        MetaData(schema="cache"),
        Column("id", Text, primary_key=True),
        Column("value", Text, nullable=False),
    )


def test_cache_session_roundtrip(pg_storage) -> None:
    _ = pg_storage
    repo = _SmokeRepo()

    def _ensure(conn) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS cache._cache_session_smoke (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
                value TEXT NOT NULL
            );
            """
        )

    def _insert(conn) -> None:
        _ensure(conn)
        conn.execute_stmt(insert(_SmokeRepo.table).values(value="ok"))

    repo.run(_insert)
    row = repo.fetchone(_SmokeRepo.table.select().order_by(_SmokeRepo.table.c.id.desc()).limit(1))
    assert row is not None
    assert row["value"] == "ok"
    _ = cache_metadata
