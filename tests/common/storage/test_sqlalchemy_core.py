"""SQLAlchemy Core 查询测试。"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from vnpy_ashare.storage.connection import get_meta, set_meta
from vnpy_common.storage.query import user_scope
from vnpy_common.storage.session import connect_app
from vnpy_common.storage.tables import meta
from vnpy_common.storage.tables import watchlist_positions as wp


def test_meta_roundtrip_via_core(pg_storage) -> None:
    _ = pg_storage
    key = f"_core_smoke_{uuid.uuid4().hex}"
    set_meta(key, "alpha")
    assert get_meta(key) == "alpha"
    set_meta(key, "beta")
    assert get_meta(key) == "beta"


def test_meta_upsert_direct(pg_storage) -> None:
    _ = pg_storage
    key = f"_core_upsert_{uuid.uuid4().hex}"
    with connect_app() as conn:
        stmt = pg_insert(meta).values(key=key, value="v1")
        stmt = stmt.on_conflict_do_update(
            index_elements=[meta.c.key],
            set_={"value": stmt.excluded.value},
        )
        conn.execute_stmt(stmt)
        row = conn.execute_stmt(select(meta.c.value).where(meta.c.key == key)).fetchone()
    assert row is not None
    assert row["value"] == "v1"


def test_user_scope_filter(pg_storage) -> None:
    _ = pg_storage
    from vnpy_ashare.storage.auth.users import get_or_create_default_user_id

    uid = get_or_create_default_user_id()
    symbol = f"T{uuid.uuid4().hex[:6].upper()}"
    with connect_app() as conn:
        conn.execute_stmt(
            pg_insert(wp).values(
                user_id=uid,
                symbol=symbol,
                exchange="SSE",
                cost_price=10.0,
                volume=100,
                buy_date="2026-01-01",
                notes="",
                source="manual",
                plan_pct=None,
                sort_order=0,
                created_at="2026-01-01T00:00:00",
                updated_at="2026-01-01T00:00:00",
            )
        )
        row = conn.execute_stmt(select(wp.c.symbol).where(user_scope(wp.c.user_id, uid, wp.c.symbol == symbol)).limit(1)).fetchone()
        assert row is not None
        assert row["symbol"] == symbol
        conn.execute_stmt(delete(wp).where(user_scope(wp.c.user_id, uid, wp.c.symbol == symbol)))
