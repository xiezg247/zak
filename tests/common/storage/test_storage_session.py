"""存储层单元测试（PostgreSQL）。"""

from __future__ import annotations

import pytest

from vnpy_common.storage.compat import DbConnection
from vnpy_common.storage.config import require_database_url
from vnpy_common.storage.postgres_backend import PostgresBackend
from vnpy_common.storage.session import connect_app


def test_require_database_url_raises_without_config(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for key in ("POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DATABASE"):
        monkeypatch.delenv(key, raising=False)
    from vnpy_common.storage.config import reset_storage_config

    reset_storage_config()
    monkeypatch.setattr("vnpy_common.storage.config._ensure_dotenv", lambda: None)
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        require_database_url()


def test_pg_connect_app_roundtrip(pg_storage) -> None:
    _ = pg_storage
    with connect_app() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _pg_only_smoke (
                id SERIAL PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute("INSERT INTO _pg_only_smoke (value) VALUES (?)", ("ok",))
    with connect_app() as conn:
        row = conn.execute("SELECT value FROM _pg_only_smoke ORDER BY id DESC LIMIT 1").fetchone()
    assert row is not None
    assert row["value"] == "ok"


def test_pg_select_string_id_does_not_break(pg_storage) -> None:
    _ = pg_storage
    with connect_app() as conn:
        row = conn.execute("SELECT id FROM sessions LIMIT 1").fetchone()
    if row is not None:
        assert isinstance(row["id"], str)


def test_pg_placeholder_compat(pg_storage) -> None:
    _ = pg_storage
    with connect_app() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _pg_placeholder_smoke (
                k TEXT PRIMARY KEY,
                v TEXT NOT NULL
            )
            """
        )
        conn.execute("INSERT INTO _pg_placeholder_smoke (k, v) VALUES (?, ?) ON CONFLICT (k) DO NOTHING", ("a", "1"))
        rows = conn.execute("SELECT k, v FROM _pg_placeholder_smoke WHERE k = ?", ("a",)).fetchall()
    assert len(rows) == 1
    assert rows[0]["v"] == "1"
