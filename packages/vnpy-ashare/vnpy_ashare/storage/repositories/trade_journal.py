"""交易流水 repository（J-02）。"""

from __future__ import annotations

from datetime import datetime

from vnpy_ashare.domain.trading.journal import TradeJournalEntry
from vnpy_ashare.storage.connection import connect, init_app_db


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_tags(text: str) -> tuple[str, ...]:
    parts = [item.strip() for item in str(text or "").split(",") if item.strip()]
    return tuple(parts)


def _tags_to_text(tags: tuple[str, ...] | list[str]) -> str:
    return ",".join(item.strip() for item in tags if item.strip())


def _row_to_entry(row) -> TradeJournalEntry:
    return TradeJournalEntry(
        id=int(row["id"]),
        symbol=str(row["symbol"]),
        exchange=str(row["exchange"]),
        side=str(row["side"]),  # type: ignore[arg-type]
        trade_date=str(row["trade_date"]),
        price=float(row["price"]),
        volume=int(row["volume"]),
        mode=str(row["mode"] or ""),
        plan_id=str(row["plan_id"]) if row["plan_id"] else None,
        on_plan=bool(int(row["on_plan"])),
        violation_tags=_parse_tags(row["violation_tags"]),
        pnl=float(row["pnl"]) if row["pnl"] is not None else None,
        pnl_pct=float(row["pnl_pct"]) if row["pnl_pct"] is not None else None,
        reason=str(row["reason"] or ""),
        emotion_stage=str(row["emotion_stage"] or ""),
        created_at=str(row["created_at"]),
    )


def insert_trade_journal_entry(
    *,
    symbol: str,
    exchange: str,
    side: str,
    trade_date: str,
    price: float,
    volume: int,
    mode: str = "",
    plan_id: str | None = None,
    on_plan: bool = True,
    violation_tags: tuple[str, ...] | list[str] = (),
    pnl: float | None = None,
    pnl_pct: float | None = None,
    reason: str = "",
    emotion_stage: str = "",
) -> int | None:
    if side not in {"buy", "sell", "hold"}:
        return None
    if side in {"buy", "sell"} and (price <= 0 or volume <= 0):
        return None
    if side == "hold" and volume <= 0:
        return None
    init_app_db()
    now = _now_iso()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO trade_journal(
                symbol, exchange, side, trade_date, price, volume, mode, plan_id,
                on_plan, violation_tags, pnl, pnl_pct, reason, emotion_stage, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                exchange,
                side,
                trade_date[:10],
                price,
                volume,
                mode.strip(),
                plan_id,
                1 if on_plan else 0,
                _tags_to_text(violation_tags),
                pnl,
                pnl_pct,
                reason.strip(),
                emotion_stage.strip(),
                now,
            ),
        )
        return int(cursor.lastrowid)


def query_trade_journal(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
) -> list[TradeJournalEntry]:
    init_app_db()
    clauses: list[str] = []
    values: list[object] = []
    if start_date:
        clauses.append("trade_date >= ?")
        values.append(start_date[:10])
    if end_date:
        clauses.append("trade_date <= ?")
        values.append(end_date[:10])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    values.append(max(1, limit))
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM trade_journal
            {where}
            ORDER BY trade_date DESC, created_at DESC
            LIMIT ?
            """,
            tuple(values),
        ).fetchall()
    return [_row_to_entry(row) for row in rows]


def summarize_trade_journal(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, int | float]:
    entries = query_trade_journal(start_date=start_date, end_date=end_date, limit=500)
    total = len(entries)
    violation_count = sum(1 for item in entries if item.violation_tags)
    off_plan_count = sum(1 for item in entries if "off_plan" in item.violation_tags)
    on_plan_count = sum(1 for item in entries if item.on_plan)
    buy_count = sum(1 for item in entries if item.side == "buy")
    sell_count = sum(1 for item in entries if item.side == "sell")
    realized = [item.pnl for item in entries if item.side == "sell" and item.pnl is not None]
    realized_total = round(sum(realized), 2) if realized else 0.0
    return {
        "total": total,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "on_plan_count": on_plan_count,
        "violation_count": violation_count,
        "off_plan_count": off_plan_count,
        "realized_pnl_total": realized_total,
    }


def count_trade_journal_for_date(trade_date: str) -> int:
    init_app_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM trade_journal WHERE trade_date = ?",
            (trade_date[:10],),
        ).fetchone()
    return int(row[0]) if row else 0


def sum_realized_pnl_for_date(trade_date: str) -> float:
    init_app_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(pnl), 0) FROM trade_journal
            WHERE trade_date = ? AND side = 'sell' AND pnl IS NOT NULL
            """,
            (trade_date[:10],),
        ).fetchone()
    return round(float(row[0]), 2) if row else 0.0


def has_sell_journal_since(
    symbol: str,
    exchange: str,
    *,
    since_date: str,
) -> bool:
    init_app_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM trade_journal
            WHERE symbol = ? AND exchange = ? AND side = 'sell' AND trade_date >= ?
            LIMIT 1
            """,
            (symbol, exchange, since_date[:10]),
        ).fetchone()
    return row is not None


def has_violation_tag_on_date(
    symbol: str,
    exchange: str,
    *,
    trade_date: str,
    tag: str,
) -> bool:
    init_app_db()
    pattern = f"%{tag}%"
    with connect() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM trade_journal
            WHERE symbol = ? AND exchange = ? AND trade_date = ?
              AND violation_tags LIKE ?
            LIMIT 1
            """,
            (symbol, exchange, trade_date[:10], pattern),
        ).fetchone()
    return row is not None


def query_latest_buy_journal(symbol: str, exchange: str) -> TradeJournalEntry | None:
    init_app_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM trade_journal
            WHERE symbol = ? AND exchange = ? AND side = 'buy'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (symbol, exchange),
        ).fetchone()
    return _row_to_entry(row) if row is not None else None
