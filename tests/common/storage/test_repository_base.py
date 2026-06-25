"""Repository 基类测试。"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from vnpy_ashare.storage.auth.users import get_or_create_default_user_id
from vnpy_ashare.storage.repositories.positions import PositionRepository
from vnpy_common.storage.repository import BaseRepository, UserScopedRepository, bulk_upsert
from vnpy_common.storage.session import connect_app
from vnpy_common.storage.tables import meta
from vnpy_common.storage.tables import valuation_history as vh
from vnpy_common.storage.tables import watchlist as wl
from vnpy_common.storage.tables import watchlist_positions as wp


class _TestUserRepo(UserScopedRepository):
    table = wp

    @staticmethod
    def user_id_resolver() -> str:
        return get_or_create_default_user_id()


def test_bulk_upsert_roundtrip(pg_storage) -> None:
    _ = pg_storage
    ts_code = f"{uuid.uuid4().hex[:6].upper()}.SH"
    with connect_app() as conn:
        bulk_upsert(
            conn,
            vh,
            [
                {
                    "ts_code": ts_code,
                    "trade_date": "20260101",
                    "close": 10.0,
                    "pe_ttm": 1.0,
                    "pb": 2.0,
                    "total_mv": 100.0,
                    "circ_mv": 50.0,
                    "turnover_rate": 0.5,
                    "fetched_at": "2026-01-01T00:00:00+00:00",
                }
            ],
            conflict_columns=("ts_code", "trade_date"),
            update_columns=("close", "fetched_at"),
        )
        row = conn.execute_stmt(
            select(vh.c.close, vh.c.fetched_at).where(
                vh.c.ts_code == ts_code,
                vh.c.trade_date == "20260101",
            )
        ).fetchone()
        assert row is not None
        assert float(row["close"]) == 10.0
        conn.execute_stmt(delete(vh).where(vh.c.ts_code == ts_code))


def test_user_scoped_repository_count(pg_storage) -> None:
    _ = pg_storage
    repo = _TestUserRepo()
    uid = repo.current_user_id()
    symbol = f"P{uuid.uuid4().hex[:5].upper()}"
    with connect_app() as conn:
        conn.execute_stmt(
            pg_insert(wl).values(
                user_id=uid,
                symbol=symbol,
                exchange="SSE",
                name="test",
                sort_order=0,
            )
        )
        conn.execute_stmt(
            insert(wp).values(
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
    assert repo.count_for_user(wp.c.symbol == symbol) == 1
    with connect_app() as conn:
        repo.delete_where(conn, repo.scope(wp.c.symbol == symbol))
        conn.execute_stmt(delete(wl).where(wl.c.user_id == uid, wl.c.symbol == symbol))


def test_position_repository_contains(pg_storage) -> None:
    _ = pg_storage
    from vnpy.trader.constant import Exchange

    from vnpy_ashare.storage.repositories import watchlist as watchlist_repo

    repo = PositionRepository()
    symbol = f"6{uuid.uuid4().int % 1000000:06d}"
    watchlist_repo.add_watchlist_item(symbol, Exchange.SSE, "测试")
    assert repo.add(
        symbol,
        Exchange.SSE,
        cost_price=10.0,
        volume=100,
        buy_date="2026-01-01",
    )
    assert repo.contains(symbol, Exchange.SSE)
    assert repo.remove(symbol, Exchange.SSE)
    watchlist_repo.remove_watchlist_item(symbol, Exchange.SSE)


def test_base_repository_meta(pg_storage) -> None:
    _ = pg_storage

    class MetaRepo(BaseRepository):
        table = meta

    repo = MetaRepo()
    key = f"_repo_{uuid.uuid4().hex}"
    repo.insert_one(key=key, value="v1")
    row = repo.fetchone(select(meta.c.value).where(meta.c.key == key))
    assert row is not None
    assert row["value"] == "v1"
    repo.delete_matching(meta.c.key == key)
