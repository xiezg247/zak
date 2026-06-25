"""全 A 股 universe repository。"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, insert, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql.elements import ColumnElement
from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.repositories.csv_io import read_stock_csv_rows, write_stock_csv
from vnpy_ashare.storage.repository.app import AppBaseRepository
from vnpy_common.storage.tables import meta
from vnpy_common.storage.tables import universe as u

UNIVERSE_SYNCED_AT_KEY = "universe_synced_at"
CACHE_MAX_AGE = timedelta(days=7)
_INSERT_CHUNK = 500

_BOARD_PREFIXES: dict[str, tuple[str, ...]] = {
    "沪深主板": ("600", "601", "603", "000", "001", "002", "003"),
    "创业板": ("300",),
    "科创板": ("688",),
    "北交所": ("8", "4"),
}


def _board_filter(board: str | None) -> ColumnElement[bool] | None:
    """板块过滤；LIKE 模式参数化，避免 PostgreSQL 将 % 解析为占位符。"""
    if not board or board == "全部":
        return None
    prefixes = _BOARD_PREFIXES.get(board)
    if not prefixes:
        return None
    return or_(*[u.c.symbol.like(f"{prefix}%") for prefix in prefixes])


class UniverseRepository(AppBaseRepository):
    table = u

    @staticmethod
    def _row_to_stock(row) -> tuple[str, Exchange, str]:
        return row["symbol"], Exchange[row["exchange"]], row["name"]

    def count_universe(self, board: str | None = None) -> int:
        stmt = select(func.count()).select_from(u)
        board_clause = _board_filter(board)
        if board_clause is not None:
            stmt = stmt.where(board_clause)
        row = self.fetchone(stmt)
        return int(row[0]) if row is not None else 0

    def load_universe_slice(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        board: str | None = None,
    ) -> list[tuple[str, Exchange, str]]:
        stmt = select(u.c.symbol, u.c.exchange, u.c.name).order_by(u.c.symbol).limit(limit).offset(offset)
        board_clause = _board_filter(board)
        if board_clause is not None:
            stmt = stmt.where(board_clause)
        rows = self.fetchall(stmt)
        return [self._row_to_stock(row) for row in rows]

    def load_universe_page(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        board: str | None = None,
    ) -> tuple[list[tuple[str, Exchange, str]], int]:
        total = self.count_universe(board)
        rows = self.load_universe_slice(offset=offset, limit=limit, board=board)
        return rows, total

    def load_universe_rows(self) -> list[tuple[str, Exchange, str]]:
        rows = self.fetchall(select(u.c.symbol, u.c.exchange, u.c.name).order_by(u.c.symbol))
        return [self._row_to_stock(row) for row in rows]

    def load_universe_names_for_keys(
        self,
        keys: list[tuple[str, Exchange]],
        *,
        chunk_size: int = 400,
    ) -> dict[tuple[str, Exchange], str]:
        """按 (symbol, exchange) 批量查名称；分页本地列表避免全表 load_universe_rows。"""
        if not keys:
            return {}
        unique_keys = list(dict.fromkeys(keys))
        result: dict[tuple[str, Exchange], str] = {}
        for start in range(0, len(unique_keys), chunk_size):
            chunk = unique_keys[start : start + chunk_size]
            key_tuples = [(symbol, exchange.name) for symbol, exchange in chunk]
            rows = self.fetchall(select(u.c.symbol, u.c.exchange, u.c.name).where(tuple_(u.c.symbol, u.c.exchange).in_(key_tuples)))
            for row in rows:
                result[(row["symbol"], Exchange[row["exchange"]])] = row["name"]
        return result

    def _replace_all(self, values: list[dict[str, str]], *, synced_at: datetime) -> int:
        def _write(conn) -> None:
            conn.execute_stmt(delete(u))
            for start in range(0, len(values), _INSERT_CHUNK):
                chunk = values[start : start + _INSERT_CHUNK]
                if chunk:
                    conn.execute_stmt(insert(u).values(chunk))
            stmt = pg_insert(meta).values(key=UNIVERSE_SYNCED_AT_KEY, value=synced_at.isoformat())
            excluded = stmt.excluded
            conn.execute_stmt(
                stmt.on_conflict_do_update(
                    index_elements=[meta.c.key],
                    set_={"value": excluded.value},
                )
            )

        self.run(_write)
        return len(values)

    def save_universe_rows(
        self,
        items: list[tuple[str, Exchange, str]],
        *,
        synced_at: datetime | None = None,
    ) -> int:
        synced_at = synced_at or datetime.now()
        values = [{"symbol": symbol, "exchange": exchange.name, "name": name} for symbol, exchange, name in items]
        return self._replace_all(values, synced_at=synced_at)

    def universe_exists(self) -> bool:
        return self.count_universe() > 0

    def universe_count(self) -> int:
        return self.count_universe()

    def search_universe(
        self,
        keyword: str,
        *,
        limit: int = 50,
        offset: int = 0,
        board: str | None = None,
    ) -> tuple[list[tuple[str, Exchange, str]], int]:
        keyword = keyword.strip().lower()
        if not keyword:
            return [], 0

        pattern = f"%{keyword}%"
        text_filter = or_(func.lower(u.c.symbol).like(pattern), func.lower(u.c.name).like(pattern))
        board_clause = _board_filter(board)
        filters: list[ColumnElement[bool]] = [text_filter]
        if board_clause is not None:
            filters.append(board_clause)

        count_row = self.fetchone(select(func.count()).select_from(u).where(*filters))
        total = int(count_row[0]) if count_row is not None else 0
        rows = self.fetchall(select(u.c.symbol, u.c.exchange, u.c.name).where(*filters).order_by(u.c.symbol).limit(limit).offset(offset))
        return [self._row_to_stock(row) for row in rows], total

    def universe_is_fresh(self, max_age: timedelta = CACHE_MAX_AGE) -> bool:
        if self.count_universe() == 0:
            return False
        row = self.fetchone(select(meta.c.value).where(meta.c.key == UNIVERSE_SYNCED_AT_KEY))
        synced_at_raw = str(row["value"]) if row else ""
        if not synced_at_raw:
            return False
        synced_at = datetime.fromisoformat(synced_at_raw)
        return datetime.now() - synced_at < max_age

    def import_universe_csv(self, path: Path) -> int:
        rows = read_stock_csv_rows(path)
        values = [{"symbol": row["symbol"], "exchange": row["exchange"], "name": row.get("name", "")} for row in rows]
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return self._replace_all(values, synced_at=mtime)

    def export_universe_csv(self, path: Path) -> int:
        items = self.load_universe_rows()
        write_stock_csv(path, items)
        return len(items)


_repo = UniverseRepository()


def count_universe(board: str | None = None) -> int:
    return _repo.count_universe(board)


def load_universe_slice(
    *,
    offset: int = 0,
    limit: int = 50,
    board: str | None = None,
) -> list[tuple[str, Exchange, str]]:
    return _repo.load_universe_slice(offset=offset, limit=limit, board=board)


def load_universe_page(
    *,
    offset: int = 0,
    limit: int = 50,
    board: str | None = None,
) -> tuple[list[tuple[str, Exchange, str]], int]:
    return _repo.load_universe_page(offset=offset, limit=limit, board=board)


def load_universe_rows() -> list[tuple[str, Exchange, str]]:
    return _repo.load_universe_rows()


def load_universe_names_for_keys(
    keys: list[tuple[str, Exchange]],
    *,
    chunk_size: int = 400,
) -> dict[tuple[str, Exchange], str]:
    return _repo.load_universe_names_for_keys(keys, chunk_size=chunk_size)


def save_universe_rows(
    items: list[tuple[str, Exchange, str]],
    *,
    synced_at: datetime | None = None,
) -> int:
    return _repo.save_universe_rows(items, synced_at=synced_at)


def universe_exists() -> bool:
    return _repo.universe_exists()


def universe_count() -> int:
    return _repo.universe_count()


def search_universe(
    keyword: str,
    *,
    limit: int = 50,
    offset: int = 0,
    board: str | None = None,
) -> tuple[list[tuple[str, Exchange, str]], int]:
    return _repo.search_universe(keyword, limit=limit, offset=offset, board=board)


def universe_is_fresh(max_age: timedelta = CACHE_MAX_AGE) -> bool:
    return _repo.universe_is_fresh(max_age)


def import_universe_csv(path: Path) -> int:
    return _repo.import_universe_csv(path)


def export_universe_csv(path: Path) -> int:
    return _repo.export_universe_csv(path)
