"""自选分组 repository。"""

from __future__ import annotations

import uuid

from pydantic import Field
from vnpy.trader.constant import Exchange

from vnpy_common.domain.base import FrozenModel
from vnpy_ashare.storage.connection import connect, init_app_db

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
    with connect() as conn:
        rows = conn.execute("SELECT id, name, sort_order, position_cap_pct FROM watchlist_groups ORDER BY sort_order, name").fetchall()
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
    with connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM watchlist_groups").fetchone()[0])


def watchlist_group_exists(group_id: str) -> bool:
    init_app_db()
    with connect() as conn:
        row = conn.execute("SELECT 1 FROM watchlist_groups WHERE id = ?", (group_id,)).fetchone()
    return row is not None


def create_watchlist_group(name: str) -> str | None:
    normalized = _normalize_group_name(name)
    if not normalized:
        return None
    if watchlist_group_count() >= WATCHLIST_MAX_GROUPS:
        return None
    init_app_db()
    group_id = uuid.uuid4().hex
    with connect() as conn:
        duplicate = conn.execute(
            "SELECT 1 FROM watchlist_groups WHERE name = ? COLLATE NOCASE",
            (normalized,),
        ).fetchone()
        if duplicate is not None:
            return None
        sort_order = conn.execute("SELECT COUNT(*) FROM watchlist_groups").fetchone()[0]
        conn.execute(
            "INSERT INTO watchlist_groups(id, name, sort_order) VALUES (?, ?, ?)",
            (group_id, normalized, int(sort_order)),
        )
    return group_id


def rename_watchlist_group(group_id: str, name: str) -> bool:
    normalized = _normalize_group_name(name)
    if not normalized or not watchlist_group_exists(group_id):
        return False
    init_app_db()
    with connect() as conn:
        duplicate = conn.execute(
            "SELECT 1 FROM watchlist_groups WHERE name = ? COLLATE NOCASE AND id <> ?",
            (normalized, group_id),
        ).fetchone()
        if duplicate is not None:
            return False
        cursor = conn.execute(
            "UPDATE watchlist_groups SET name = ? WHERE id = ?",
            (normalized, group_id),
        )
    return bool(cursor.rowcount > 0)


def delete_watchlist_group(group_id: str) -> bool:
    if not watchlist_group_exists(group_id):
        return False
    init_app_db()
    with connect() as conn:
        conn.execute("DELETE FROM watchlist_groups WHERE id = ?", (group_id,))
        rows = conn.execute("SELECT id, name, sort_order FROM watchlist_groups ORDER BY sort_order, name").fetchall()
        for index, row in enumerate(rows):
            conn.execute(
                "UPDATE watchlist_groups SET sort_order = ? WHERE id = ?",
                (index, row["id"]),
            )
    return True


def add_watchlist_group_member(group_id: str, symbol: str, exchange: Exchange) -> bool:
    if not watchlist_group_exists(group_id):
        return False
    init_app_db()
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM watchlist WHERE symbol = ? AND exchange = ?",
            (symbol, exchange.name),
        ).fetchone()
        if exists is None:
            return False
        conn.execute(
            """
            INSERT OR IGNORE INTO watchlist_group_members(group_id, symbol, exchange)
            VALUES (?, ?, ?)
            """,
            (group_id, symbol, exchange.name),
        )
    return True


def remove_watchlist_group_member(group_id: str, symbol: str, exchange: Exchange) -> bool:
    init_app_db()
    with connect() as conn:
        cursor = conn.execute(
            """
            DELETE FROM watchlist_group_members
            WHERE group_id = ? AND symbol = ? AND exchange = ?
            """,
            (group_id, symbol, exchange.name),
        )
    return bool(cursor.rowcount > 0)


def update_watchlist_group_position_cap(group_id: str, position_cap_pct: float | None) -> bool:
    if not watchlist_group_exists(group_id):
        return False
    cap = _parse_cap_pct(position_cap_pct)
    init_app_db()
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE watchlist_groups SET position_cap_pct = ? WHERE id = ?",
            (cap, group_id),
        )
    return bool(cursor.rowcount > 0)


def load_watchlist_group_member_keys(group_id: str) -> set[tuple[str, str]]:
    init_app_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT symbol, exchange FROM watchlist_group_members
            WHERE group_id = ?
            """,
            (group_id,),
        ).fetchall()
    return {(str(row["symbol"]), str(row["exchange"])) for row in rows}


def load_watchlist_group_ids_for_item(symbol: str, exchange: Exchange) -> set[str]:
    init_app_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT group_id FROM watchlist_group_members
            WHERE symbol = ? AND exchange = ?
            """,
            (symbol, exchange.name),
        ).fetchall()
    return {str(row["group_id"]) for row in rows}


def set_watchlist_group_membership(symbol: str, exchange: Exchange, group_ids: set[str]) -> None:
    init_app_db()
    with connect() as conn:
        conn.execute(
            "DELETE FROM watchlist_group_members WHERE symbol = ? AND exchange = ?",
            (symbol, exchange.name),
        )
        for group_id in sorted(group_ids):
            if not watchlist_group_exists(group_id):
                continue
            conn.execute(
                """
                INSERT OR IGNORE INTO watchlist_group_members(group_id, symbol, exchange)
                VALUES (?, ?, ?)
                """,
                (group_id, symbol, exchange.name),
            )


def _prune_watchlist_group_members_conn(conn) -> None:
    conn.execute(
        """
        DELETE FROM watchlist_group_members
        WHERE NOT EXISTS (
            SELECT 1 FROM watchlist w
            WHERE w.symbol = watchlist_group_members.symbol
              AND w.exchange = watchlist_group_members.exchange
        )
        """
    )


def prune_watchlist_group_members() -> None:
    init_app_db()
    with connect() as conn:
        _prune_watchlist_group_members_conn(conn)


def remove_watchlist_group_members_for_item(symbol: str, exchange: Exchange) -> None:
    init_app_db()
    with connect() as conn:
        conn.execute(
            "DELETE FROM watchlist_group_members WHERE symbol = ? AND exchange = ?",
            (symbol, exchange.name),
        )
