"""自选分组 repository。"""

from __future__ import annotations

import uuid

from pydantic import Field
from sqlalchemy import delete, exists, func, select, update
from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.repository.app import AppUserScopedRepository
from vnpy_common.domain.base import FrozenModel
from vnpy_common.storage.query import user_scope
from vnpy_common.storage.repository import insert_ignore
from vnpy_common.storage.tables import watchlist as wl
from vnpy_common.storage.tables import watchlist_group_members as wgm
from vnpy_common.storage.tables import watchlist_groups as wg

WATCHLIST_MAX_GROUPS = 10

_GROUP_COLUMNS = (wg.c.id, wg.c.name, wg.c.sort_order, wg.c.position_cap_pct)


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


class WatchlistGroupRepository(AppUserScopedRepository):
    table = wg

    def load_groups(self) -> list[WatchlistGroupRecord]:
        rows = self.list_for_user(*_GROUP_COLUMNS, order_by=(wg.c.sort_order, wg.c.name))
        return [
            WatchlistGroupRecord(
                id=str(row["id"]),
                name=str(row["name"]),
                sort_order=int(row["sort_order"]),
                position_cap_pct=_parse_cap_pct(row["position_cap_pct"] if "position_cap_pct" in row.keys() else None),
            )
            for row in rows
        ]

    def group_count(self) -> int:
        return self.count_for_user()

    def group_exists(self, group_id: str) -> bool:
        return self.exists_for_user(wg.c.id == group_id)

    def _name_taken(self, name: str, *, exclude_id: str | None = None) -> bool:
        extras = [func.lower(wg.c.name) == name.lower()]
        if exclude_id is not None:
            extras.append(wg.c.id != exclude_id)
        return self.exists_for_user(*extras)

    def create_group(self, name: str) -> str | None:
        normalized = _normalize_group_name(name)
        if not normalized:
            return None
        if self.group_count() >= WATCHLIST_MAX_GROUPS:
            return None
        if self._name_taken(normalized):
            return None
        group_id = uuid.uuid4().hex
        self.insert_one_for_user(id=group_id, name=normalized, sort_order=self.group_count())
        return group_id

    def rename_group(self, group_id: str, name: str) -> bool:
        normalized = _normalize_group_name(name)
        if not normalized or not self.group_exists(group_id):
            return False
        if self._name_taken(normalized, exclude_id=group_id):
            return False
        return self.update_matching({"name": normalized}, self.scope(wg.c.id == group_id)) > 0

    def delete_group(self, group_id: str) -> bool:
        if not self.group_exists(group_id):
            return False

        def _write(conn) -> None:
            conn.execute_stmt(delete(wgm).where(self.scope_table(wgm, wgm.c.group_id == group_id)))
            self.delete_where(conn, self.scope(wg.c.id == group_id))
            rows = conn.execute_stmt(
                self.select_columns(
                    wg.c.id,
                    wg.c.name,
                    wg.c.sort_order,
                    where=(self.scope(),),
                    order_by=(wg.c.sort_order, wg.c.name),
                )
            ).fetchall()
            for index, row in enumerate(rows):
                conn.execute_stmt(
                    update(wg).where(self.scope(wg.c.id == row["id"])).values(sort_order=index)
                )

        self.run(_write)
        return True

    def add_member(self, group_id: str, symbol: str, exchange: Exchange) -> bool:
        if not self.group_exists(group_id):
            return False

        def _write(conn) -> bool:
            in_watchlist = conn.execute_stmt(
                select(1)
                .select_from(wl)
                .where(self.scope_table(wl, (wl.c.symbol == symbol) & (wl.c.exchange == exchange.name)))
                .limit(1)
            ).fetchone()
            if in_watchlist is None:
                return False
            insert_ignore(
                conn,
                wgm,
                {
                    "user_id": self.current_user_id(),
                    "group_id": group_id,
                    "symbol": symbol,
                    "exchange": exchange.name,
                },
            )
            return True

        return bool(self.run(_write))

    def remove_member(self, group_id: str, symbol: str, exchange: Exchange) -> bool:
        return (
            self.delete_matching(
                self.scope_table(
                    wgm,
                    (wgm.c.group_id == group_id)
                    & (wgm.c.symbol == symbol)
                    & (wgm.c.exchange == exchange.name),
                )
            )
            > 0
        )

    def update_position_cap(self, group_id: str, position_cap_pct: float | None) -> bool:
        if not self.group_exists(group_id):
            return False
        cap = _parse_cap_pct(position_cap_pct)
        return self.update_matching({"position_cap_pct": cap}, self.scope(wg.c.id == group_id)) > 0

    def load_member_keys(self, group_id: str) -> set[tuple[str, str]]:
        rows = self.fetchall(
            select(wgm.c.symbol, wgm.c.exchange).where(self.scope_table(wgm, wgm.c.group_id == group_id))
        )
        return {(str(row["symbol"]), str(row["exchange"])) for row in rows}

    def load_group_ids_for_item(self, symbol: str, exchange: Exchange) -> set[str]:
        rows = self.fetchall(
            select(wgm.c.group_id).where(
                self.scope_table(wgm, (wgm.c.symbol == symbol) & (wgm.c.exchange == exchange.name))
            )
        )
        return {str(row["group_id"]) for row in rows}

    def set_membership(self, symbol: str, exchange: Exchange, group_ids: set[str]) -> None:
        def _write(conn) -> None:
            conn.execute_stmt(
                delete(wgm).where(
                    self.scope_table(wgm, (wgm.c.symbol == symbol) & (wgm.c.exchange == exchange.name))
                )
            )
            uid = self.current_user_id()
            for group_id in sorted(group_ids):
                if not self.group_exists(group_id):
                    continue
                insert_ignore(
                    conn,
                    wgm,
                    {
                        "user_id": uid,
                        "group_id": group_id,
                        "symbol": symbol,
                        "exchange": exchange.name,
                    },
                )

        self.run(_write)

    def prune_members(self) -> None:
        self.run(lambda conn: _prune_watchlist_group_members_conn(conn, self.current_user_id()))

    def remove_members_for_item(self, symbol: str, exchange: Exchange) -> None:
        self.delete_matching(
            self.scope_table(wgm, (wgm.c.symbol == symbol) & (wgm.c.exchange == exchange.name))
        )


def _prune_watchlist_group_members_conn(conn, uid: str) -> None:
    watchlist_exists = exists(
        select(1).select_from(wl).where(
            wl.c.user_id == wgm.c.user_id,
            wl.c.symbol == wgm.c.symbol,
            wl.c.exchange == wgm.c.exchange,
        )
    )
    conn.execute_stmt(delete(wgm).where(user_scope(wgm.c.user_id, uid), ~watchlist_exists))


_repo = WatchlistGroupRepository()


def load_watchlist_groups() -> list[WatchlistGroupRecord]:
    return _repo.load_groups()


def watchlist_group_count() -> int:
    return _repo.group_count()


def watchlist_group_exists(group_id: str) -> bool:
    return _repo.group_exists(group_id)


def create_watchlist_group(name: str) -> str | None:
    return _repo.create_group(name)


def rename_watchlist_group(group_id: str, name: str) -> bool:
    return _repo.rename_group(group_id, name)


def delete_watchlist_group(group_id: str) -> bool:
    return _repo.delete_group(group_id)


def add_watchlist_group_member(group_id: str, symbol: str, exchange: Exchange) -> bool:
    return _repo.add_member(group_id, symbol, exchange)


def remove_watchlist_group_member(group_id: str, symbol: str, exchange: Exchange) -> bool:
    return _repo.remove_member(group_id, symbol, exchange)


def update_watchlist_group_position_cap(group_id: str, position_cap_pct: float | None) -> bool:
    return _repo.update_position_cap(group_id, position_cap_pct)


def load_watchlist_group_member_keys(group_id: str) -> set[tuple[str, str]]:
    return _repo.load_member_keys(group_id)


def load_watchlist_group_ids_for_item(symbol: str, exchange: Exchange) -> set[str]:
    return _repo.load_group_ids_for_item(symbol, exchange)


def set_watchlist_group_membership(symbol: str, exchange: Exchange, group_ids: set[str]) -> None:
    _repo.set_membership(symbol, exchange, group_ids)


def prune_watchlist_group_members() -> None:
    _repo.prune_members()


def remove_watchlist_group_members_for_item(symbol: str, exchange: Exchange) -> None:
    _repo.remove_members_for_item(symbol, exchange)
