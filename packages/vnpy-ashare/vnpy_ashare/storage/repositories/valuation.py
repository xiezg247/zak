"""估值历史 repository。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import Field
from sqlalchemy import Table, select

from vnpy_ashare.domain.core.numbers import coerce_float
from vnpy_common.domain.base import FrozenModel
from vnpy_ashare.storage.repository.app import AppBaseRepository
from vnpy_common.storage.repository import bulk_upsert
from vnpy_common.storage.tables import valuation_history as vh

_VALUATION_COLUMNS = (
    vh.c.ts_code,
    vh.c.trade_date,
    vh.c.close,
    vh.c.pe_ttm,
    vh.c.pb,
    vh.c.total_mv,
    vh.c.circ_mv,
    vh.c.turnover_rate,
    vh.c.fetched_at,
)

_UPSERT_UPDATE_COLUMNS = (
    "close",
    "pe_ttm",
    "pb",
    "total_mv",
    "circ_mv",
    "turnover_rate",
    "fetched_at",
)


class ValuationRow(FrozenModel):
    ts_code: str = Field(description="Tushare 证券代码")
    trade_date: str = Field(description="交易日 YYYYMMDD")
    close: float | None = Field(description="收盘价")
    pe_ttm: float | None = Field(description="市盈率 TTM")
    pb: float | None = Field(description="市净率")
    total_mv: float | None = Field(description="总市值")
    circ_mv: float | None = Field(description="流通市值")
    turnover_rate: float | None = Field(description="换手率")
    fetched_at: str = Field(description="抓取时间 ISO")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ValuationRepository(AppBaseRepository):
    table: Table = vh

    def upsert_rows(self, ts_code: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        fetched_at = _now_iso()
        values = [
            {
                "ts_code": ts_code,
                "trade_date": str(row.get("trade_date", "")),
                "close": coerce_float(row.get("close")),
                "pe_ttm": coerce_float(row.get("pe_ttm")),
                "pb": coerce_float(row.get("pb")),
                "total_mv": coerce_float(row.get("total_mv")),
                "circ_mv": coerce_float(row.get("circ_mv")),
                "turnover_rate": coerce_float(row.get("turnover_rate")),
                "fetched_at": fetched_at,
            }
            for row in rows
            if row.get("trade_date")
        ]
        if not values:
            return 0

        def _write(conn) -> None:
            bulk_upsert(
                conn,
                self.table,
                values,
                conflict_columns=("ts_code", "trade_date"),
                update_columns=_UPSERT_UPDATE_COLUMNS,
            )

        self.run(_write)
        return len(values)

    def list_history(self, ts_code: str, limit: int = 750) -> list[ValuationRow]:
        rows = self.fetchall(
            self.select_columns(
                *_VALUATION_COLUMNS,
                where=(vh.c.ts_code == ts_code,),
                order_by=(vh.c.trade_date.desc(),),
                limit=limit,
            )
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
            for row in rows
        ]

    def latest_trade_date(self, ts_code: str) -> str | None:
        row = self.fetchone(
            select(vh.c.trade_date)
            .where(vh.c.ts_code == ts_code)
            .order_by(vh.c.trade_date.desc())
            .limit(1)
        )
        return str(row["trade_date"]) if row else None


_repo = ValuationRepository()


def upsert_valuation_rows(ts_code: str, rows: list[dict[str, Any]]) -> int:
    return _repo.upsert_rows(ts_code, rows)


def list_valuation_history(ts_code: str, limit: int = 750) -> list[ValuationRow]:
    return _repo.list_history(ts_code, limit)


def latest_valuation_trade_date(ts_code: str) -> str | None:
    return _repo.latest_trade_date(ts_code)
