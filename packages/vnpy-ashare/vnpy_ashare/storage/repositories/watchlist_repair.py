"""自选池证券名称修复（一次性运维脚本，不在运行时调用）。"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select, update
from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.repositories.universe import load_universe_names_for_keys
from vnpy_ashare.storage.repositories.watchlist import WatchlistRepository
from vnpy_common.storage.query import user_scope
from vnpy_common.storage.tables import watchlist as wl


@dataclass
class WatchlistNamePatch:
    user_id: str
    username: str
    symbol: str
    exchange: Exchange
    old_name: str
    new_name: str
    source: str


@dataclass
class WatchlistRepairReport:
    patches: list[WatchlistNamePatch] = field(default_factory=list)
    dry_run: bool = False

    @property
    def updated_count(self) -> int:
        return len(self.patches)

    def summary_lines(self) -> list[str]:
        prefix = "[dry-run] " if self.dry_run else ""
        lines = [f"{prefix}共修复 {self.updated_count} 条自选名称"]
        for patch in self.patches:
            label = f"{patch.symbol}.{patch.exchange.value}"
            lines.append(f"  [{patch.username}] {label}: {patch.old_name!r} → {patch.new_name!r} ({patch.source})")
        if not self.patches:
            lines.append("  无需修复")
        return lines


def _resolve_name(
    symbol: str,
    exchange: Exchange,
    *,
    universe_names: dict[tuple[str, Exchange], str],
) -> tuple[str, str] | None:
    universe = universe_names.get((symbol, exchange), "")
    if universe:
        return universe, "universe"
    return None


def repair_watchlist_names_for_user(
    user_id: str,
    username: str,
    *,
    dry_run: bool = False,
) -> list[WatchlistNamePatch]:
    """仅补全 name 为空的自选行；已有名称不覆盖。"""
    patches: list[WatchlistNamePatch] = []
    repo = WatchlistRepository()

    rows = repo.fetchall(select(wl.c.symbol, wl.c.exchange, wl.c.name).where(user_scope(wl.c.user_id, user_id)).order_by(wl.c.sort_order, wl.c.symbol))

    missing: list[tuple[str, Exchange, str]] = []
    for row in rows:
        name = str(row["name"] or "").strip()
        if name:
            continue
        missing.append((str(row["symbol"]), Exchange[row["exchange"]], name))

    if not missing:
        return patches

    universe_names = load_universe_names_for_keys([(symbol, exchange) for symbol, exchange, _ in missing])

    for symbol, exchange, old_name in missing:
        resolved = _resolve_name(symbol, exchange, universe_names=universe_names)
        if resolved is None:
            continue
        new_name, source = resolved
        patches.append(
            WatchlistNamePatch(
                user_id=user_id,
                username=username,
                symbol=symbol,
                exchange=exchange,
                old_name=old_name,
                new_name=new_name,
                source=source,
            )
        )

    if dry_run or not patches:
        return patches

    def _write(conn) -> None:
        for patch in patches:
            conn.execute_stmt(
                update(wl)
                .where(
                    user_scope(
                        wl.c.user_id,
                        user_id,
                        wl.c.symbol == patch.symbol,
                        wl.c.exchange == patch.exchange.name,
                    )
                )
                .values(name=patch.new_name)
            )

    repo.run(_write)
    return patches


def repair_all_watchlist_names(*, dry_run: bool = False) -> WatchlistRepairReport:
    """修复所有用户的自选名称（仅补空名）。"""
    from vnpy_ashare.storage.auth.users import list_users

    report = WatchlistRepairReport(dry_run=dry_run)
    users = list_users()

    if not users:
        from vnpy_ashare.storage.auth.scope import get_user_id

        uid = get_user_id()
        patches = repair_watchlist_names_for_user(uid, "default", dry_run=dry_run)
        report.patches.extend(patches)
        return report

    for user in users:
        patches = repair_watchlist_names_for_user(
            user.id,
            user.username,
            dry_run=dry_run,
        )
        report.patches.extend(patches)
    return report
