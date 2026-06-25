"""板块资金盘中采样（概览折线）。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from vnpy_ashare.domain.market.sector_flow import SectorFlowRow
from vnpy_ashare.storage.repository.app import AppBaseRepository
from vnpy_common.storage.repository import bulk_upsert
from vnpy_common.storage.tables import sector_flow_intraday as sfi

_INTRADAY_COLUMNS = (
    sfi.c.sector_id,
    sfi.c.name,
    sfi.c.bucket_time,
    sfi.c.clock_minutes,
    sfi.c.net_flow_yi,
    sfi.c.change_pct,
)

_UPSERT_UPDATE_COLUMNS = ("name", "clock_minutes", "net_flow_yi", "change_pct")


@dataclass(frozen=True)
class SectorFlowIntradayRecord:
    sector_id: str
    name: str
    bucket_time: str
    clock_minutes: int
    net_flow_yi: float
    change_pct: float


class SectorFlowIntradayRepository(AppBaseRepository):
    table = sfi

    def purge_before(self, trade_date: str) -> None:
        day = str(trade_date or "").strip()
        if not day:
            return
        self.delete_matching(sfi.c.trade_date < day)

    def upsert_samples(
        self,
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
        values = [
            {
                "trade_date": day,
                "sector_kind": kind,
                "sector_id": row.sector_id,
                "name": row.name,
                "bucket_time": bucket,
                "clock_minutes": int(clock_minutes),
                "net_flow_yi": float(row.net_flow_yi),
                "change_pct": float(row.change_pct),
            }
            for row in rows
        ]

        def _write(conn) -> None:
            bulk_upsert(
                conn,
                self.table,
                values,
                conflict_columns=("trade_date", "sector_kind", "sector_id", "bucket_time"),
                update_columns=_UPSERT_UPDATE_COLUMNS,
            )

        self.run(_write)

    def load_records(self, *, trade_date: str, sector_kind: str) -> list[SectorFlowIntradayRecord]:
        day = str(trade_date or "").strip()
        kind = str(sector_kind or "industry").strip().lower()
        if not day:
            return []
        rows = self.fetchall(
            select(*_INTRADAY_COLUMNS).where(sfi.c.trade_date == day, sfi.c.sector_kind == kind).order_by(sfi.c.sector_id.asc(), sfi.c.clock_minutes.asc())
        )
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


_repo = SectorFlowIntradayRepository()


def purge_intraday_before(trade_date: str) -> None:
    _repo.purge_before(trade_date)


def upsert_intraday_samples(
    trade_date: str,
    sector_kind: str,
    rows: list[SectorFlowRow],
    *,
    bucket_time: str,
    clock_minutes: int,
) -> None:
    _repo.upsert_samples(
        trade_date,
        sector_kind,
        rows,
        bucket_time=bucket_time,
        clock_minutes=clock_minutes,
    )


def load_intraday_records(
    *,
    trade_date: str,
    sector_kind: str,
) -> list[SectorFlowIntradayRecord]:
    return _repo.load_records(trade_date=trade_date, sector_kind=sector_kind)
