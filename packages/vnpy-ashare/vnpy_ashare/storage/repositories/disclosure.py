"""财报披露计划 repository。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import Field
from sqlalchemy import select

from vnpy_ashare.storage.repository.app import AppBaseRepository
from vnpy_common.domain.base import FrozenModel
from vnpy_common.storage.repository import bulk_upsert
from vnpy_common.storage.tables import disclosure_calendar as dc

_DISCLOSURE_COLUMNS = (
    dc.c.ts_code,
    dc.c.end_date,
    dc.c.pre_date,
    dc.c.ann_date,
    dc.c.actual_date,
    dc.c.fetched_at,
)

_UPSERT_UPDATE_COLUMNS = ("pre_date", "ann_date", "actual_date", "fetched_at")


class DisclosureRow(FrozenModel):
    ts_code: str = Field(description="Tushare 证券代码")
    end_date: str = Field(description="报告期截止日")
    pre_date: str = Field(description="预计披露日")
    ann_date: str = Field(description="公告披露日")
    actual_date: str = Field(description="实际披露日")
    fetched_at: str = Field(description="抓取时间 ISO")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class DisclosureRepository(AppBaseRepository):
    table = dc

    def upsert_rows(self, ts_code: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        fetched_at = _now_iso()
        values = [
            {
                "ts_code": ts_code,
                "end_date": str(row.get("end_date", "")),
                "pre_date": str(row.get("pre_date") or ""),
                "ann_date": str(row.get("ann_date") or ""),
                "actual_date": str(row.get("actual_date") or ""),
                "fetched_at": fetched_at,
            }
            for row in rows
            if row.get("end_date")
        ]
        if not values:
            return 0

        def _write(conn) -> None:
            bulk_upsert(
                conn,
                self.table,
                values,
                conflict_columns=("ts_code", "end_date"),
                update_columns=_UPSERT_UPDATE_COLUMNS,
            )

        self.run(_write)
        return len(values)

    def list_calendar(self, ts_code: str, limit: int = 8) -> list[DisclosureRow]:
        rows = self.fetchall(
            self.select_columns(
                *_DISCLOSURE_COLUMNS,
                where=(dc.c.ts_code == ts_code,),
                order_by=(dc.c.end_date.desc(),),
                limit=limit,
            )
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
            for row in rows
        ]

    def latest_ann_date_after(self, ts_code: str, since_yyyymmdd: str) -> str | None:
        row = self.fetchone(select(dc.c.ann_date).where(dc.c.ts_code == ts_code, dc.c.ann_date > since_yyyymmdd).order_by(dc.c.ann_date.desc()).limit(1))
        if not row or not row["ann_date"]:
            return None
        return str(row["ann_date"])


_repo = DisclosureRepository()


def upsert_disclosure_rows(ts_code: str, rows: list[dict[str, Any]]) -> int:
    return _repo.upsert_rows(ts_code, rows)


def list_disclosure_calendar(ts_code: str, limit: int = 8) -> list[DisclosureRow]:
    return _repo.list_calendar(ts_code, limit)


def latest_ann_date_after(ts_code: str, since_yyyymmdd: str) -> str | None:
    return _repo.latest_ann_date_after(ts_code, since_yyyymmdd)
