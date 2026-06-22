"""板块资金盘中采样（概览折线）。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_ashare.domain.market.sector_flow import SectorFlowRow
from vnpy_ashare.storage.connection import connect, init_app_db


@dataclass(frozen=True)
class SectorFlowIntradayRecord:
    sector_id: str
    name: str
    bucket_time: str
    clock_minutes: int
    net_flow_yi: float
    change_pct: float


def purge_intraday_before(trade_date: str) -> None:
    """删除早于指定交易日的盘中采样。"""
    day = str(trade_date or "").strip()
    if not day:
        return
    init_app_db()
    with connect() as conn:
        conn.execute("DELETE FROM sector_flow_intraday WHERE trade_date < ?", (day,))


def upsert_intraday_samples(
    trade_date: str,
    sector_kind: str,
    rows: list[SectorFlowRow],
    *,
    bucket_time: str,
    clock_minutes: int,
) -> None:
    day = str(trade_date or "").strip()
    kind = str(sector_kind or "industry").strip().lower()
    bucket = str(bucket_time or "").strip()
    if not day or not bucket or not rows:
        return
    init_app_db()
    payload = [
        (
            day,
            kind,
            row.sector_id,
            row.name,
            bucket,
            int(clock_minutes),
            float(row.net_flow_yi),
            float(row.change_pct),
        )
        for row in rows
    ]
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO sector_flow_intraday(
                trade_date, sector_kind, sector_id, name,
                bucket_time, clock_minutes, net_flow_yi, change_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trade_date, sector_kind, sector_id, bucket_time) DO UPDATE SET
                name = excluded.name,
                clock_minutes = excluded.clock_minutes,
                net_flow_yi = excluded.net_flow_yi,
                change_pct = excluded.change_pct
            """,
            payload,
        )


def load_intraday_records(
    *,
    trade_date: str,
    sector_kind: str,
) -> list[SectorFlowIntradayRecord]:
    day = str(trade_date or "").strip()
    kind = str(sector_kind or "industry").strip().lower()
    if not day:
        return []
    init_app_db()
    with connect() as conn:
        cursor = conn.execute(
            """
            SELECT sector_id, name, bucket_time, clock_minutes, net_flow_yi, change_pct
            FROM sector_flow_intraday
            WHERE trade_date = ? AND sector_kind = ?
            ORDER BY sector_id ASC, clock_minutes ASC
            """,
            (day, kind),
        )
        rows = list(cursor.fetchall())
    return [
        SectorFlowIntradayRecord(
            sector_id=str(row["sector_id"]),
            name=str(row["name"]),
            bucket_time=str(row["bucket_time"]),
            clock_minutes=int(row["clock_minutes"] or 0),
            net_flow_yi=float(row["net_flow_yi"] or 0),
            change_pct=float(row["change_pct"] or 0),
        )
        for row in rows
    ]
