"""个股笔记 repository（备忘 + 流水）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import insert, select, text, update
from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.repository.app import AppUserScopedRepository
from vnpy_common.storage.tables import stock_note_entries as sne
from vnpy_common.storage.tables import stock_note_memos as snm

ENTRY_MAX_BODY = 2000
MEMO_MAX_BODY = 32000

_ENTRY_COLUMNS = (sne.c.id, sne.c.symbol, sne.c.exchange, sne.c.body, sne.c.created_at)
_MEMO_COLUMNS = (snm.c.symbol, snm.c.exchange, snm.c.body, snm.c.updated_at)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clip_body(body: str, max_len: int) -> str:
    text_body = body.strip()
    if len(text_body) <= max_len:
        return text_body
    return text_body[:max_len]


def _preview_text(body: str, max_len: int = 96) -> str:
    text_body = " ".join(line.strip() for line in body.strip().splitlines() if line.strip())
    if len(text_body) <= max_len:
        return text_body
    return text_body[:max_len] + "…"


class StockNoteRepository(AppUserScopedRepository):
    table = snm

    def _item_filter(self, symbol: str, exchange: Exchange):
        return (snm.c.symbol == symbol) & (snm.c.exchange == exchange.name)

    def load_memo(self, symbol: str, exchange: Exchange) -> dict[str, str] | None:
        rows = self.list_for_user(*_MEMO_COLUMNS, extras=(self._item_filter(symbol, exchange),), limit=1)
        if not rows:
            return None
        row = rows[0]
        return {
            "symbol": row["symbol"],
            "exchange": row["exchange"],
            "body": row["body"] or "",
            "updated_at": row["updated_at"],
        }

    def upsert_memo(self, symbol: str, exchange: Exchange, body: str) -> None:
        text_body = _clip_body(body, MEMO_MAX_BODY)
        now = _now_iso()

        def _write(conn) -> None:
            if self.exists_for_user(self._item_filter(symbol, exchange)):
                conn.execute_stmt(
                    update(snm)
                    .where(self.scope(self._item_filter(symbol, exchange)))
                    .values(body=text_body, updated_at=now)
                )
            else:
                self.insert_for_user(
                    conn,
                    symbol=symbol,
                    exchange=exchange.name,
                    body=text_body,
                    updated_at=now,
                )

        self.run(_write)

    def append_entry(self, symbol: str, exchange: Exchange, body: str) -> dict[str, str | int] | None:
        text_body = _clip_body(body, ENTRY_MAX_BODY)
        if not text_body:
            return None
        now = _now_iso()

        def _write(conn):
            row = conn.execute_stmt(
                insert(sne)
                .values(
                    user_id=self.current_user_id(),
                    symbol=symbol,
                    exchange=exchange.name,
                    body=text_body,
                    created_at=now,
                )
                .returning(sne.c.id)
            ).fetchone()
            return row

        row = self.run(_write)
        if row is None:
            return None
        return {
            "id": int(row["id"]),
            "symbol": symbol,
            "exchange": exchange.name,
            "body": text_body,
            "created_at": now,
        }

    def list_entries(self, symbol: str, exchange: Exchange, limit: int = 50) -> list[dict[str, str | int]]:
        limit = max(1, min(int(limit), 200))
        rows = self.fetchall(
            select(*_ENTRY_COLUMNS)
            .where(self.scope_table(sne, (sne.c.symbol == symbol) & (sne.c.exchange == exchange.name)))
            .order_by(sne.c.created_at.desc(), sne.c.id.desc())
            .limit(limit)
        )
        return [
            {
                "id": int(row["id"]),
                "symbol": row["symbol"],
                "exchange": row["exchange"],
                "body": row["body"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def delete_entry(self, entry_id: int) -> bool:
        return self.delete_matching(self.scope_table(sne, sne.c.id == int(entry_id))) > 0

    def get_entry(self, entry_id: int) -> dict[str, str | int] | None:
        rows = self.fetchall(
            select(*_ENTRY_COLUMNS).where(self.scope_table(sne, sne.c.id == int(entry_id))).limit(1)
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "id": int(row["id"]),
            "symbol": row["symbol"],
            "exchange": row["exchange"],
            "body": row["body"],
            "created_at": row["created_at"],
        }

    def clear_for_symbol(self, symbol: str, exchange: Exchange) -> dict[str, int]:
        def _write(conn) -> dict[str, int]:
            memo_count = self.delete_where(conn, self.scope(self._item_filter(symbol, exchange)))
            entry_count = self.delete_where(
                conn,
                self.scope_table(sne, (sne.c.symbol == symbol) & (sne.c.exchange == exchange.name)),
            )
            return {"memos": memo_count, "entries": entry_count}

        return self.run(_write)

    def list_symbols_with_notes(self) -> list[tuple[str, str]]:
        uid = self.current_user_id()
        stmt = text(
            """
            SELECT symbol, exchange FROM stock_note_memos
            WHERE user_id = :uid AND TRIM(body) != ''
            UNION
            SELECT symbol, exchange FROM stock_note_entries WHERE user_id = :uid
            UNION
            SELECT symbol, exchange FROM stock_analysis_reports WHERE user_id = :uid
            ORDER BY symbol, exchange
            """
        ).bindparams(uid=uid)
        rows = self.fetchall(stmt)
        return [(row["symbol"], row["exchange"]) for row in rows]

    def list_note_index_rows(self) -> list[dict[str, str | int]]:
        uid = self.current_user_id()
        stmt = text(
            """
            WITH symbols AS (
                SELECT symbol, exchange FROM stock_note_memos
                WHERE user_id = :uid AND TRIM(body) != ''
                UNION
                SELECT symbol, exchange FROM stock_note_entries WHERE user_id = :uid
                UNION
                SELECT symbol, exchange FROM stock_analysis_reports WHERE user_id = :uid
            )
            SELECT
                s.symbol,
                s.exchange,
                COALESCE(m.body, '') AS memo_body,
                COALESCE(m.updated_at, '') AS memo_updated_at,
                (
                    SELECT COUNT(*)
                    FROM stock_note_entries e
                    WHERE e.user_id = :uid AND e.symbol = s.symbol AND e.exchange = s.exchange
                ) AS entry_count,
                (
                    SELECT MAX(created_at)
                    FROM stock_note_entries e
                    WHERE e.user_id = :uid AND e.symbol = s.symbol AND e.exchange = s.exchange
                ) AS latest_entry_at,
                (
                    SELECT COUNT(*)
                    FROM stock_analysis_reports r
                    WHERE r.user_id = :uid AND r.symbol = s.symbol AND r.exchange = s.exchange
                ) AS report_count,
                (
                    SELECT MAX(created_at)
                    FROM stock_analysis_reports r
                    WHERE r.user_id = :uid AND r.symbol = s.symbol AND r.exchange = s.exchange
                ) AS latest_report_at
            FROM symbols s
            LEFT JOIN stock_note_memos m
                ON m.user_id = :uid AND m.symbol = s.symbol AND m.exchange = s.exchange
            ORDER BY s.symbol, s.exchange
            """
        ).bindparams(uid=uid)
        rows = self.fetchall(stmt)
        result: list[dict[str, str | int]] = []
        for row in rows:
            memo_body = str(row["memo_body"] or "")
            memo_updated = str(row["memo_updated_at"] or "")
            latest_entry = str(row["latest_entry_at"] or "")
            latest_report = str(row["latest_report_at"] or "")
            entry_count = int(row["entry_count"] or 0)
            report_count = int(row["report_count"] or 0)
            activity_candidates = [t for t in (memo_updated, latest_entry, latest_report) if t]
            last_activity = max(activity_candidates) if activity_candidates else ""
            result.append(
                {
                    "symbol": row["symbol"],
                    "exchange": row["exchange"],
                    "memo_body": memo_body,
                    "memo_preview": _preview_text(memo_body),
                    "has_memo": bool(memo_body.strip()),
                    "entry_count": entry_count,
                    "report_count": report_count,
                    "memo_updated_at": memo_updated,
                    "latest_entry_at": latest_entry,
                    "latest_report_at": latest_report,
                    "last_activity_at": last_activity,
                }
            )
        result.sort(key=lambda item: str(item["last_activity_at"]), reverse=True)
        return result


_repo = StockNoteRepository()


def load_memo(symbol: str, exchange: Exchange) -> dict[str, str] | None:
    return _repo.load_memo(symbol, exchange)


def upsert_memo(symbol: str, exchange: Exchange, body: str) -> None:
    _repo.upsert_memo(symbol, exchange, body)


def append_entry(symbol: str, exchange: Exchange, body: str) -> dict[str, str | int] | None:
    return _repo.append_entry(symbol, exchange, body)


def list_entries(symbol: str, exchange: Exchange, limit: int = 50) -> list[dict[str, str | int]]:
    return _repo.list_entries(symbol, exchange, limit)


def delete_entry(entry_id: int) -> bool:
    return _repo.delete_entry(entry_id)


def get_entry(entry_id: int) -> dict[str, str | int] | None:
    return _repo.get_entry(entry_id)


def clear_notes_for_symbol(symbol: str, exchange: Exchange) -> dict[str, int]:
    return _repo.clear_for_symbol(symbol, exchange)


def list_symbols_with_notes() -> list[tuple[str, str]]:
    return _repo.list_symbols_with_notes()


def list_note_index_rows() -> list[dict[str, str | int]]:
    return _repo.list_note_index_rows()
