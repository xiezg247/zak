"""个股笔记 repository（备忘 + 流水）。"""

from __future__ import annotations

from datetime import datetime

from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.connection import connect, init_app_db

ENTRY_MAX_BODY = 2000
MEMO_MAX_BODY = 32000


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clip_body(body: str, max_len: int) -> str:
    text = body.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len]


def load_memo(symbol: str, exchange: Exchange) -> dict[str, str] | None:
    init_app_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT symbol, exchange, body, updated_at FROM stock_note_memos WHERE symbol = ? AND exchange = ?",
            (symbol, exchange.name),
        ).fetchone()
    if row is None:
        return None
    return {
        "symbol": row["symbol"],
        "exchange": row["exchange"],
        "body": row["body"] or "",
        "updated_at": row["updated_at"],
    }


def upsert_memo(symbol: str, exchange: Exchange, body: str) -> None:
    text = _clip_body(body, MEMO_MAX_BODY)
    now = _now_iso()
    init_app_db()
    with connect() as conn:
        conn.execute(
            "INSERT INTO stock_note_memos(symbol, exchange, body, updated_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(symbol, exchange) DO UPDATE SET "
            "body = excluded.body, updated_at = excluded.updated_at",
            (symbol, exchange.name, text, now),
        )


def append_entry(symbol: str, exchange: Exchange, body: str) -> dict[str, str | int] | None:
    text = _clip_body(body, ENTRY_MAX_BODY)
    if not text:
        return None
    now = _now_iso()
    init_app_db()
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO stock_note_entries(symbol, exchange, body, created_at) VALUES (?, ?, ?, ?)",
            (symbol, exchange.name, text, now),
        )
        return {
            "id": int(cursor.lastrowid),
            "symbol": symbol,
            "exchange": exchange.name,
            "body": text,
            "created_at": now,
        }


def list_entries(symbol: str, exchange: Exchange, limit: int = 50) -> list[dict[str, str | int]]:
    limit = max(1, min(int(limit), 200))
    init_app_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, symbol, exchange, body, created_at FROM stock_note_entries WHERE symbol = ? AND exchange = ? ORDER BY created_at DESC, id DESC LIMIT ?",
            (symbol, exchange.name, limit),
        ).fetchall()
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


def delete_entry(entry_id: int) -> bool:
    init_app_db()
    with connect() as conn:
        cursor = conn.execute("DELETE FROM stock_note_entries WHERE id = ?", (int(entry_id),))
    return bool(cursor.rowcount > 0)


def get_entry(entry_id: int) -> dict[str, str | int] | None:
    init_app_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT id, symbol, exchange, body, created_at FROM stock_note_entries WHERE id = ?",
            (int(entry_id),),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "symbol": row["symbol"],
        "exchange": row["exchange"],
        "body": row["body"],
        "created_at": row["created_at"],
    }


def clear_notes_for_symbol(symbol: str, exchange: Exchange) -> dict[str, int]:
    init_app_db()
    with connect() as conn:
        memo_cursor = conn.execute(
            "DELETE FROM stock_note_memos WHERE symbol = ? AND exchange = ?",
            (symbol, exchange.name),
        )
        entry_cursor = conn.execute(
            "DELETE FROM stock_note_entries WHERE symbol = ? AND exchange = ?",
            (symbol, exchange.name),
        )
    return {
        "memos": int(memo_cursor.rowcount),
        "entries": int(entry_cursor.rowcount),
    }


def list_symbols_with_notes() -> list[tuple[str, str]]:
    init_app_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT symbol, exchange FROM stock_note_memos WHERE TRIM(body) != ''
            UNION
            SELECT symbol, exchange FROM stock_note_entries
            UNION
            SELECT symbol, exchange FROM stock_analysis_reports
            ORDER BY symbol, exchange
            """
        ).fetchall()
    return [(row["symbol"], row["exchange"]) for row in rows]


def list_note_index_rows() -> list[dict[str, str | int]]:
    """按标的聚合备忘与流水数量，供笔记中心列表使用。"""
    init_app_db()
    with connect() as conn:
        rows = conn.execute(
            """
            WITH symbols AS (
                SELECT symbol, exchange FROM stock_note_memos WHERE TRIM(body) != ''
                UNION
                SELECT symbol, exchange FROM stock_note_entries
                UNION
                SELECT symbol, exchange FROM stock_analysis_reports
            )
            SELECT
                s.symbol,
                s.exchange,
                COALESCE(m.body, '') AS memo_body,
                COALESCE(m.updated_at, '') AS memo_updated_at,
                (
                    SELECT COUNT(*)
                    FROM stock_note_entries e
                    WHERE e.symbol = s.symbol AND e.exchange = s.exchange
                ) AS entry_count,
                (
                    SELECT MAX(created_at)
                    FROM stock_note_entries e
                    WHERE e.symbol = s.symbol AND e.exchange = s.exchange
                ) AS latest_entry_at,
                (
                    SELECT COUNT(*)
                    FROM stock_analysis_reports r
                    WHERE r.symbol = s.symbol AND r.exchange = s.exchange
                ) AS report_count,
                (
                    SELECT MAX(created_at)
                    FROM stock_analysis_reports r
                    WHERE r.symbol = s.symbol AND r.exchange = s.exchange
                ) AS latest_report_at
            FROM symbols s
            LEFT JOIN stock_note_memos m
                ON m.symbol = s.symbol AND m.exchange = s.exchange
            ORDER BY s.symbol, s.exchange
            """
        ).fetchall()
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


def _preview_text(body: str, max_len: int = 96) -> str:
    text = " ".join(line.strip() for line in body.strip().splitlines() if line.strip())
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"
