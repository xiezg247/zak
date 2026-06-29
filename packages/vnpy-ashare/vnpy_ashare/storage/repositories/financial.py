"""个股财报 repository。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from vnpy_ashare.storage.repository.app import AppBaseRepository
from vnpy_common.domain.base import MutableModel
from vnpy_common.storage.compat import DbRow
from vnpy_common.storage.tables import financial_reports as fr
from vnpy_common.storage.tables import financial_snapshots as fs
from vnpy_common.storage.tables import financial_sync_meta as fsm

REPORT_TYPES: tuple[str, ...] = (
    "income",
    "balancesheet",
    "cashflow",
    "fina_indicator",
    "express",
    "forecast",
    "mainbz_p",
    "mainbz_d",
)

_REPORT_UPSERT_COLUMNS = ("ann_date", "period", "source", "fetched_at", "payload")
_SNAPSHOT_UPSERT_COLUMNS = (
    "revenue",
    "net_income",
    "operate_profit",
    "basic_eps",
    "total_assets",
    "total_liab",
    "total_equity",
    "ocf",
    "icf",
    "fcf_flow",
    "free_cashflow",
    "roe",
    "gross_margin",
    "net_margin",
    "debt_ratio",
    "current_ratio",
    "revenue_yoy",
    "net_income_yoy",
    "roe_yoy",
    "ocf_to_profit",
    "computed_at",
)
_SYNC_META_UPSERT_COLUMNS = (
    "last_sync_at",
    "latest_end_date",
    "latest_ann_date",
    "sync_status",
    "error_message",
    "periods_count",
    "last_access_at",
)


class FinancialSyncMeta(MutableModel):
    ts_code: str = Field(description="Tushare 证券代码")
    last_sync_at: str = Field(description="上次同步时间")
    latest_end_date: str = Field(default="", description="最新报告期")
    latest_ann_date: str = Field(default="", description="最新公告日")
    sync_status: str = Field(default="ok", description="同步状态")
    error_message: str = Field(default="", description="错误信息")
    periods_count: int = Field(default=0, description="已同步期数")
    last_access_at: str = Field(default="", description="上次访问时间")


class FinancialSnapshotRow(MutableModel):
    ts_code: str = Field(description="Tushare 证券代码")
    end_date: str = Field(description="报告期截止日")
    revenue: float | None = Field(default=None, description="营业收入")
    net_income: float | None = Field(default=None, description="净利润")
    operate_profit: float | None = Field(default=None, description="营业利润")
    basic_eps: float | None = Field(default=None, description="基本每股收益")
    total_assets: float | None = Field(default=None, description="总资产")
    total_liab: float | None = Field(default=None, description="总负债")
    total_equity: float | None = Field(default=None, description="股东权益")
    ocf: float | None = Field(default=None, description="经营现金流")
    icf: float | None = Field(default=None, description="投资现金流")
    fcf_flow: float | None = Field(default=None, description="筹资现金流")
    free_cashflow: float | None = Field(default=None, description="自由现金流")
    roe: float | None = Field(default=None, description="净资产收益率")
    gross_margin: float | None = Field(default=None, description="毛利率")
    net_margin: float | None = Field(default=None, description="净利率")
    debt_ratio: float | None = Field(default=None, description="资产负债率")
    current_ratio: float | None = Field(default=None, description="流动比率")
    revenue_yoy: float | None = Field(default=None, description="营收同比")
    net_income_yoy: float | None = Field(default=None, description="净利润同比")
    roe_yoy: float | None = Field(default=None, description="ROE 同比")
    ocf_to_profit: float | None = Field(default=None, description="经营现金流/净利润")
    computed_at: str = Field(default="", description="计算时间")


def _row_to_snapshot(row: DbRow) -> FinancialSnapshotRow:
    def _opt(key: str) -> float | None:
        value = row[key]
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    return FinancialSnapshotRow(
        ts_code=str(row["ts_code"]),
        end_date=str(row["end_date"]),
        revenue=_opt("revenue"),
        net_income=_opt("net_income"),
        operate_profit=_opt("operate_profit"),
        basic_eps=_opt("basic_eps"),
        total_assets=_opt("total_assets"),
        total_liab=_opt("total_liab"),
        total_equity=_opt("total_equity"),
        ocf=_opt("ocf"),
        icf=_opt("icf"),
        fcf_flow=_opt("fcf_flow"),
        free_cashflow=_opt("free_cashflow"),
        roe=_opt("roe"),
        gross_margin=_opt("gross_margin"),
        net_margin=_opt("net_margin"),
        debt_ratio=_opt("debt_ratio"),
        current_ratio=_opt("current_ratio"),
        revenue_yoy=_opt("revenue_yoy"),
        net_income_yoy=_opt("net_income_yoy"),
        roe_yoy=_opt("roe_yoy"),
        ocf_to_profit=_opt("ocf_to_profit"),
        computed_at=str(row["computed_at"]),
    )


def _snapshot_values(row: FinancialSnapshotRow, computed_at: str) -> dict[str, Any]:
    return {
        "ts_code": row.ts_code,
        "end_date": row.end_date,
        "revenue": row.revenue,
        "net_income": row.net_income,
        "operate_profit": row.operate_profit,
        "basic_eps": row.basic_eps,
        "total_assets": row.total_assets,
        "total_liab": row.total_liab,
        "total_equity": row.total_equity,
        "ocf": row.ocf,
        "icf": row.icf,
        "fcf_flow": row.fcf_flow,
        "free_cashflow": row.free_cashflow,
        "roe": row.roe,
        "gross_margin": row.gross_margin,
        "net_margin": row.net_margin,
        "debt_ratio": row.debt_ratio,
        "current_ratio": row.current_ratio,
        "revenue_yoy": row.revenue_yoy,
        "net_income_yoy": row.net_income_yoy,
        "roe_yoy": row.roe_yoy,
        "ocf_to_profit": row.ocf_to_profit,
        "computed_at": computed_at,
    }


class FinancialRepository(AppBaseRepository):
    table = fr

    def upsert_report(
        self,
        *,
        ts_code: str,
        report_type: str,
        end_date: str,
        ann_date: str,
        period: str,
        payload: dict[str, Any],
        source: str = "tushare",
    ) -> None:
        fetched_at = datetime.now().isoformat(timespec="seconds")
        values = {
            "ts_code": ts_code,
            "report_type": report_type,
            "end_date": end_date,
            "ann_date": ann_date,
            "period": period,
            "source": source,
            "fetched_at": fetched_at,
            "payload": json.dumps(payload, ensure_ascii=False),
        }

        def _write(conn) -> None:
            stmt = pg_insert(fr).values(values)
            excluded = stmt.excluded
            conn.execute_stmt(
                stmt.on_conflict_do_update(
                    index_elements=[fr.c.ts_code, fr.c.report_type, fr.c.end_date],
                    set_={column: excluded[column] for column in _REPORT_UPSERT_COLUMNS},
                )
            )

        self.run(_write)

    def list_reports(
        self,
        ts_code: str,
        report_type: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        rows = self.fetchall(
            select(
                fr.c.end_date,
                fr.c.ann_date,
                fr.c.period,
                fr.c.source,
                fr.c.fetched_at,
                fr.c.payload,
            )
            .where(fr.c.ts_code == ts_code, fr.c.report_type == report_type)
            .order_by(fr.c.end_date.desc())
            .limit(max(1, limit))
        )
        result: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(str(row["payload"]))
            if not isinstance(payload, dict):
                payload = {}
            result.append(
                {
                    "end_date": str(row["end_date"]),
                    "ann_date": str(row["ann_date"]),
                    "period": str(row["period"]),
                    "source": str(row["source"]),
                    "fetched_at": str(row["fetched_at"]),
                    "fields": payload,
                }
            )
        return result

    def upsert_snapshot(self, row: FinancialSnapshotRow) -> None:
        computed_at = row.computed_at or datetime.now().isoformat(timespec="seconds")
        values = _snapshot_values(row, computed_at)

        def _write(conn) -> None:
            stmt = pg_insert(fs).values(values)
            excluded = stmt.excluded
            conn.execute_stmt(
                stmt.on_conflict_do_update(
                    index_elements=[fs.c.ts_code, fs.c.end_date],
                    set_={column: excluded[column] for column in _SNAPSHOT_UPSERT_COLUMNS},
                )
            )

        self.run(_write)

    def list_snapshots(self, ts_code: str, *, limit: int = 12) -> list[FinancialSnapshotRow]:
        rows = self.fetchall(select(fs).where(fs.c.ts_code == ts_code).order_by(fs.c.end_date.desc()).limit(max(1, limit)))
        return [_row_to_snapshot(row) for row in rows]

    def get_sync_meta(self, ts_code: str) -> FinancialSyncMeta | None:
        row = self.fetchone(select(fsm).where(fsm.c.ts_code == ts_code))
        if row is None:
            return None
        return FinancialSyncMeta(
            ts_code=str(row["ts_code"]),
            last_sync_at=str(row["last_sync_at"]),
            latest_end_date=str(row["latest_end_date"] or ""),
            latest_ann_date=str(row["latest_ann_date"] or ""),
            sync_status=str(row["sync_status"] or "ok"),
            error_message=str(row["error_message"] or ""),
            periods_count=int(row["periods_count"] or 0),
            last_access_at=str(row["last_access_at"] or ""),
        )

    def upsert_sync_meta(self, meta: FinancialSyncMeta) -> None:
        values = meta.model_dump()

        def _write(conn) -> None:
            stmt = pg_insert(fsm).values(values)
            excluded = stmt.excluded
            conn.execute_stmt(
                stmt.on_conflict_do_update(
                    index_elements=[fsm.c.ts_code],
                    set_={column: excluded[column] for column in _SYNC_META_UPSERT_COLUMNS},
                )
            )

        self.run(_write)

    def touch_access(self, ts_code: str) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        meta = self.get_sync_meta(ts_code)
        if meta is None:
            self.upsert_sync_meta(
                FinancialSyncMeta(
                    ts_code=ts_code,
                    last_sync_at="",
                    last_access_at=now,
                )
            )
            return
        meta.last_access_at = now
        self.upsert_sync_meta(meta)


_repo = FinancialRepository()


def upsert_report(
    *,
    ts_code: str,
    report_type: str,
    end_date: str,
    ann_date: str,
    period: str,
    payload: dict[str, Any],
    source: str = "tushare",
) -> None:
    _repo.upsert_report(
        ts_code=ts_code,
        report_type=report_type,
        end_date=end_date,
        ann_date=ann_date,
        period=period,
        payload=payload,
        source=source,
    )


def list_reports(
    ts_code: str,
    report_type: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    return _repo.list_reports(ts_code, report_type, limit=limit)


def upsert_snapshot(row: FinancialSnapshotRow) -> None:
    _repo.upsert_snapshot(row)


def list_snapshots(ts_code: str, *, limit: int = 12) -> list[FinancialSnapshotRow]:
    return _repo.list_snapshots(ts_code, limit=limit)


def get_sync_meta(ts_code: str) -> FinancialSyncMeta | None:
    return _repo.get_sync_meta(ts_code)


def upsert_sync_meta(meta: FinancialSyncMeta) -> None:
    _repo.upsert_sync_meta(meta)


def touch_access(ts_code: str) -> None:
    _repo.touch_access(ts_code)
