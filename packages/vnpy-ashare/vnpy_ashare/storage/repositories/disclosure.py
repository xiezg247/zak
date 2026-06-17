"""财报披露计划 repository。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel
from vnpy_ashare.storage.connection import connect


class DisclosureRow(FrozenModel):
    ts_code: str = Field(description="Tushare 证券代码")
    end_date: str = Field(description="报告期截止日")
    pre_date: str = Field(description="预计披露日")
    ann_date: str = Field(description="公告披露日")
    actual_date: str = Field(description="实际披露日")
    fetched_at: str = Field(description="抓取时间 ISO")


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
    with connect() as conn:
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
    with connect() as conn:
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
    with connect() as conn:
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
