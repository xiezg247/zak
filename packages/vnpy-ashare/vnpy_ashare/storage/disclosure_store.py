"""财报披露计划落盘。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from vnpy_ashare.storage.app_db import _connect


@dataclass(frozen=True)
class DisclosureRow:
    ts_code: str
    end_date: str
    pre_date: str
    ann_date: str
    actual_date: str
    fetched_at: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def upsert_disclosure_rows(ts_code: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    fetched_at = _now_iso()
    payload = [
        (
            ts_code,
            str(row.get("end_date", "")),
            str(row.get("pre_date") or ""),
            str(row.get("ann_date") or ""),
            str(row.get("actual_date") or ""),
            fetched_at,
        )
        for row in rows
        if row.get("end_date")
    ]
    if not payload:
        return 0
    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO disclosure_calendar (
                ts_code, end_date, pre_date, ann_date, actual_date, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ts_code, end_date) DO UPDATE SET
                pre_date=excluded.pre_date,
                ann_date=excluded.ann_date,
                actual_date=excluded.actual_date,
                fetched_at=excluded.fetched_at
            """,
            payload,
        )
    return len(payload)


def list_disclosure_calendar(ts_code: str, limit: int = 8) -> list[DisclosureRow]:
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT ts_code, end_date, pre_date, ann_date, actual_date, fetched_at
            FROM disclosure_calendar
            WHERE ts_code = ?
            ORDER BY end_date DESC
            LIMIT ?
            """,
            (ts_code, limit),
        )
        return [
            DisclosureRow(
                ts_code=row["ts_code"],
                end_date=row["end_date"],
                pre_date=row["pre_date"],
                ann_date=row["ann_date"],
                actual_date=row["actual_date"],
                fetched_at=row["fetched_at"],
            )
            for row in cur.fetchall()
        ]


def latest_ann_date_after(ts_code: str, since_yyyymmdd: str) -> str | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT ann_date FROM disclosure_calendar
            WHERE ts_code = ? AND ann_date > ?
            ORDER BY ann_date DESC
            LIMIT 1
            """,
            (ts_code, since_yyyymmdd),
        ).fetchone()
    if not row or not row["ann_date"]:
        return None
    return str(row["ann_date"])
