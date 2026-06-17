"""估值历史 repository。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from vnpy_ashare.domain.format import coerce_float
from vnpy_ashare.storage.connection import connect


@dataclass(frozen=True)
class ValuationRow:
    ts_code: str
    trade_date: str
    close: float | None
    pe_ttm: float | None
    pb: float | None
    total_mv: float | None
    circ_mv: float | None
    turnover_rate: float | None
    fetched_at: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def upsert_valuation_rows(ts_code: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    fetched_at = _now_iso()
    payload = [
        (
            ts_code,
            str(row.get("trade_date", "")),
            coerce_float(row.get("close")),
            coerce_float(row.get("pe_ttm")),
            coerce_float(row.get("pb")),
            coerce_float(row.get("total_mv")),
            coerce_float(row.get("circ_mv")),
            coerce_float(row.get("turnover_rate")),
            fetched_at,
        )
        for row in rows
        if row.get("trade_date")
    ]
    if not payload:
        return 0
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO valuation_history (
                ts_code, trade_date, close, pe_ttm, pb, total_mv, circ_mv,
                turnover_rate, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ts_code, trade_date) DO UPDATE SET
                close=excluded.close,
                pe_ttm=excluded.pe_ttm,
                pb=excluded.pb,
                total_mv=excluded.total_mv,
                circ_mv=excluded.circ_mv,
                turnover_rate=excluded.turnover_rate,
                fetched_at=excluded.fetched_at
            """,
            payload,
        )
    return len(payload)


def list_valuation_history(ts_code: str, limit: int = 750) -> list[ValuationRow]:
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT ts_code, trade_date, close, pe_ttm, pb, total_mv, circ_mv,
                   turnover_rate, fetched_at
            FROM valuation_history
            WHERE ts_code = ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            (ts_code, limit),
        )
        return [
            ValuationRow(
                ts_code=row["ts_code"],
                trade_date=row["trade_date"],
                close=row["close"],
                pe_ttm=row["pe_ttm"],
                pb=row["pb"],
                total_mv=row["total_mv"],
                circ_mv=row["circ_mv"],
                turnover_rate=row["turnover_rate"],
                fetched_at=row["fetched_at"],
            )
            for row in cur.fetchall()
        ]


def latest_valuation_trade_date(ts_code: str) -> str | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT trade_date FROM valuation_history
            WHERE ts_code = ?
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            (ts_code,),
        ).fetchone()
    return str(row["trade_date"]) if row else None
