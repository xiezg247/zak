"""cache schema 清理任务测试。"""

from __future__ import annotations

from datetime import datetime, timedelta

import tests._bootstrap  # noqa: F401
from vnpy_ashare.jobs.cache.purge_stale import purge_stale_cache_job
from vnpy_common.storage.session import cache_session


def _insert_signal_row(*, vt_symbol: str, updated_at: str) -> None:
    with cache_session("", "") as conn:
        conn.execute(
            """
            INSERT INTO watchlist_signal_cache (
                vt_symbol, config_key, bar_as_of, payload, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (vt_symbol, config_key, bar_as_of) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (vt_symbol, "cfg", "2026-06-26", "{}", updated_at),
        )


def test_purge_stale_cache_removes_old_signal_rows(pg_storage) -> None:
    _ = pg_storage
    old = (datetime.now() - timedelta(days=30)).isoformat(timespec="seconds")
    fresh = datetime.now().isoformat(timespec="seconds")
    _insert_signal_row(vt_symbol="000001.SSE", updated_at=old)
    _insert_signal_row(vt_symbol="600000.SSE", updated_at=fresh)

    result = purge_stale_cache_job()
    assert result.success is True

    with cache_session("", "") as conn:
        rows = conn.execute("SELECT vt_symbol FROM watchlist_signal_cache ORDER BY vt_symbol").fetchall()
    symbols = [str(row["vt_symbol"]) for row in rows]
    assert "000001.SSE" not in symbols
    assert "600000.SSE" in symbols
