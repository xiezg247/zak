"""自选分组 repository。"""

from __future__ import annotations

import uuid

from pydantic import Field
from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.auth.scope import get_user_id
from vnpy_ashare.storage.connection import connect, init_app_db
from vnpy_common.auth.scope import user_sql
from vnpy_common.domain.base import FrozenModel

WATCHLIST_MAX_GROUPS = 10


class WatchlistGroupRecord(FrozenModel):
    id: str = Field(description="分组主键")
    name: str = Field(description="分组名称")
    sort_order: int = Field(description="排序序号")
    position_cap_pct: float | None = Field(default=None, description="组内单票仓位上限（0-1）")


def _parse_cap_pct(value: object) -> float | None:
    if value is None:
        return None
    try:
        pct = float(str(value))
    except (TypeError, ValueError):
        return None
    if pct <= 0 or pct > 1:
        return None
    return round(pct, 4)


def _normalize_group_name(name: str) -> str:
    return str(name or "").strip()


def load_watchlist_groups() -> list[WatchlistGroupRecord]:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        rows = conn.execute(
            f"SELECT id, name, sort_order, position_cap_pct FROM watchlist_groups WHERE {user_sql()} ORDER BY sort_order, name",
            (uid,),
        ).fetchall()
    return [
        WatchlistGroupRecord(
            id=str(row["id"]),
            name=str(row["name"]),
            sort_order=int(row["sort_order"]),
            position_cap_pct=_parse_cap_pct(row["position_cap_pct"] if "position_cap_pct" in row.keys() else None),
        )
        for row in rows
    ]


def watchlist_group_count() -> int:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM watchlist_groups WHERE {user_sql()}", (uid,)).fetchone()[0])


def watchlist_group_exists(group_id: str) -> bool:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        row = conn.execute(
            f"SELECT 1 FROM watchlist_groups WHERE {user_sql('id = ?')}",
            (uid, group_id),
        ).fetchone()
    return row is not None


def create_watchlist_group(name: str) -> str | None:
    normalized = _normalize_group_name(name)
    if not normalized:
        return None
    if watchlist_group_count() >= WATCHLIST_MAX_GROUPS:
        return None
    init_app_db()
    uid = get_user_id()
    group_id = uuid.uuid4().hex
    with connect() as conn:
        duplicate = conn.execute(
            f"SELECT 1 FROM watchlist_groups WHERE {user_sql('name = ? COLLATE NOCASE')}",
            (uid, normalized),
        ).fetchone()
        if duplicate is not None:
            return None
        sort_order = conn.execute(f"SELECT COUNT(*) FROM watchlist_groups WHERE {user_sql()}", (uid,)).fetchone()[0]
        conn.execute(
            "INSERT INTO watchlist_groups(user_id, id, name, sort_order) VALUES (?, ?, ?, ?)",
            (uid, group_id, normalized, int(sort_order)),
        )
    return group_id


def rename_watchlist_group(group_id: str, name: str) -> bool:
    normalized = _normalize_group_name(name)
    if not normalized or not watchlist_group_exists(group_id):
        return False
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        duplicate = conn.execute(
            f"SELECT 1 FROM watchlist_groups WHERE {user_sql('name = ? COLLATE NOCASE AND id <> ?')}",
            (uid, normalized, group_id),
        ).fetchone()
        if duplicate is not None:
            return False
        cursor = conn.execute(
            f"UPDATE watchlist_groups SET name = ? WHERE {user_sql('id = ?')}",
            (normalized, uid, group_id),
        )
    return bool(cursor.rowcount > 0)


def delete_watchlist_group(group_id: str) -> bool:
    if not watchlist_group_exists(group_id):
        return False
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        conn.execute(f"DELETE FROM watchlist_group_members WHERE {user_sql('group_id = ?')}", (uid, group_id))
        conn.execute(f"DELETE FROM watchlist_groups WHERE {user_sql('id = ?')}", (uid, group_id))
        rows = conn.execute(
            f"SELECT id, name, sort_order FROM watchlist_groups WHERE {user_sql()} ORDER BY sort_order, name",
            (uid,),
        ).fetchall()
        for index, row in enumerate(rows):
            conn.execute(
                f"UPDATE watchlist_groups SET sort_order = ? WHERE {user_sql('id = ?')}",
                (index, uid, row["id"]),
            )
    return True


def add_watchlist_group_member(group_id: str, symbol: str, exchange: Exchange) -> bool:
    if not watchlist_group_exists(group_id):
        return False
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        exists = conn.execute(
            f"SELECT 1 FROM watchlist WHERE {user_sql('symbol = ? AND exchange = ?')}",
            (uid, symbol, exchange.name),
        ).fetchone()
        if exists is None:
            return False
        conn.execute(
            """
            INSERT OR IGNORE INTO watchlist_group_members(user_id, group_id, symbol, exchange)
            VALUES (?, ?, ?, ?)
            """,
            (uid, group_id, symbol, exchange.name),
        )
    return True


def remove_watchlist_group_member(group_id: str, symbol: str, exchange: Exchange) -> bool:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        cursor = conn.execute(
            f"""
            DELETE FROM watchlist_group_members
            WHERE {user_sql('group_id = ? AND symbol = ? AND exchange = ?')}
            """,
            (uid, group_id, symbol, exchange.name),
        )
    return bool(cursor.rowcount > 0)


def update_watchlist_group_position_cap(group_id: str, position_cap_pct: float | None) -> bool:
    if not watchlist_group_exists(group_id):
        return False
    cap = _parse_cap_pct(position_cap_pct)
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        cursor = conn.execute(
            f"UPDATE watchlist_groups SET position_cap_pct = ? WHERE {user_sql('id = ?')}",
            (cap, uid, group_id),
        )
    return bool(cursor.rowcount > 0)


def load_watchlist_group_member_keys(group_id: str) -> set[tuple[str, str]]:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT symbol, exchange FROM watchlist_group_members
            WHERE {user_sql('group_id = ?')}
            """,
            (uid, group_id),
        ).fetchall()
    return {(str(row["symbol"]), str(row["exchange"])) for row in rows}


def load_watchlist_group_ids_for_item(symbol: str, exchange: Exchange) -> set[str]:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT group_id FROM watchlist_group_members
            WHERE {user_sql('symbol = ? AND exchange = ?')}
            """,
            (uid, symbol, exchange.name),
        ).fetchall()
    return {str(row["group_id"]) for row in rows}


def set_watchlist_group_membership(symbol: str, exchange: Exchange, group_ids: set[str]) -> None:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        conn.execute(
            f"DELETE FROM watchlist_group_members WHERE {user_sql('symbol = ? AND exchange = ?')}",
            (uid, symbol, exchange.name),
        )
        for group_id in sorted(group_ids):
            if not watchlist_group_exists(group_id):
                continue
            conn.execute(
                """
                INSERT OR IGNORE INTO watchlist_group_members(user_id, group_id, symbol, exchange)
                VALUES (?, ?, ?, ?)
                """,
                (uid, group_id, symbol, exchange.name),
            )


def _prune_watchlist_group_members_conn(conn, uid: str) -> None:
    conn.execute(
        f"""
        DELETE FROM watchlist_group_members
        WHERE {user_sql()} AND NOT EXISTS (
            SELECT 1 FROM watchlist w
            WHERE w.user_id = watchlist_group_members.user_id
              AND w.symbol = watchlist_group_members.symbol
              AND w.exchange = watchlist_group_members.exchange
        )
        """,
        (uid,),
    )


def prune_watchlist_group_members() -> None:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        _prune_watchlist_group_members_conn(conn, uid)


def remove_watchlist_group_members_for_item(symbol: str, exchange: Exchange) -> None:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        conn.execute(
            f"DELETE FROM watchlist_group_members WHERE {user_sql('symbol = ? AND exchange = ?')}",
            (uid, symbol, exchange.name),
        )
