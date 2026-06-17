"""个股财报 repository。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from pydantic import Field

from vnpy_ashare.domain.base import MutableModel
from vnpy_ashare.storage.connection import connect

REPORT_TYPES: tuple[str, ...] = (
    "income",
    "balancesheet",
    "cashflow",
    "fina_indicator",
    "express",
    "forecast",
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
    fetched_at = datetime.now().isoformat(timespec="seconds")
    body = json.dumps(payload, ensure_ascii=False)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO financial_reports(
                ts_code, report_type, end_date, ann_date, period, source, fetched_at, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ts_code, report_type, end_date) DO UPDATE SET
                ann_date = excluded.ann_date,
                period = excluded.period,
                source = excluded.source,
                fetched_at = excluded.fetched_at,
                payload = excluded.payload
            """,
            (ts_code, report_type, end_date, ann_date, period, source, fetched_at, body),
        )


def list_reports(
    ts_code: str,
    report_type: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT end_date, ann_date, period, source, fetched_at, payload
            FROM financial_reports
            WHERE ts_code = ? AND report_type = ?
            ORDER BY end_date DESC
            LIMIT ?
            """,
            (ts_code, report_type, max(1, limit)),
        ).fetchall()
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


def upsert_snapshot(row: FinancialSnapshotRow) -> None:
    computed_at = row.computed_at or datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO financial_snapshots(
                ts_code, end_date, revenue, net_income, operate_profit, basic_eps,
                total_assets, total_liab, total_equity, ocf, icf, fcf_flow, free_cashflow,
                roe, gross_margin, net_margin, debt_ratio, current_ratio,
                revenue_yoy, net_income_yoy, roe_yoy, ocf_to_profit, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ts_code, end_date) DO UPDATE SET
                revenue = excluded.revenue,
                net_income = excluded.net_income,
                operate_profit = excluded.operate_profit,
                basic_eps = excluded.basic_eps,
                total_assets = excluded.total_assets,
                total_liab = excluded.total_liab,
                total_equity = excluded.total_equity,
                ocf = excluded.ocf,
                icf = excluded.icf,
                fcf_flow = excluded.fcf_flow,
                free_cashflow = excluded.free_cashflow,
                roe = excluded.roe,
                gross_margin = excluded.gross_margin,
                net_margin = excluded.net_margin,
                debt_ratio = excluded.debt_ratio,
                current_ratio = excluded.current_ratio,
                revenue_yoy = excluded.revenue_yoy,
                net_income_yoy = excluded.net_income_yoy,
                roe_yoy = excluded.roe_yoy,
                ocf_to_profit = excluded.ocf_to_profit,
                computed_at = excluded.computed_at
            """,
            (
                row.ts_code,
                row.end_date,
                row.revenue,
                row.net_income,
                row.operate_profit,
                row.basic_eps,
                row.total_assets,
                row.total_liab,
                row.total_equity,
                row.ocf,
                row.icf,
                row.fcf_flow,
                row.free_cashflow,
                row.roe,
                row.gross_margin,
                row.net_margin,
                row.debt_ratio,
                row.current_ratio,
                row.revenue_yoy,
                row.net_income_yoy,
                row.roe_yoy,
                row.ocf_to_profit,
                computed_at,
            ),
        )


def list_snapshots(ts_code: str, *, limit: int = 12) -> list[FinancialSnapshotRow]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM financial_snapshots
            WHERE ts_code = ?
            ORDER BY end_date DESC
            LIMIT ?
            """,
            (ts_code, max(1, limit)),
        ).fetchall()
    return [_row_to_snapshot(row) for row in rows]


def _row_to_snapshot(row: sqlite3.Row) -> FinancialSnapshotRow:
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


def get_sync_meta(ts_code: str) -> FinancialSyncMeta | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM financial_sync_meta WHERE ts_code = ?",
            (ts_code,),
        ).fetchone()
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


def upsert_sync_meta(meta: FinancialSyncMeta) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO financial_sync_meta(
                ts_code, last_sync_at, latest_end_date, latest_ann_date,
                sync_status, error_message, periods_count, last_access_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ts_code) DO UPDATE SET
                last_sync_at = excluded.last_sync_at,
                latest_end_date = excluded.latest_end_date,
                latest_ann_date = excluded.latest_ann_date,
                sync_status = excluded.sync_status,
                error_message = excluded.error_message,
                periods_count = excluded.periods_count,
                last_access_at = excluded.last_access_at
            """,
            (
                meta.ts_code,
                meta.last_sync_at,
                meta.latest_end_date,
                meta.latest_ann_date,
                meta.sync_status,
                meta.error_message,
                meta.periods_count,
                meta.last_access_at,
            ),
        )


def touch_access(ts_code: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    meta = get_sync_meta(ts_code)
    if meta is None:
        upsert_sync_meta(
            FinancialSyncMeta(
                ts_code=ts_code,
                last_sync_at="",
                last_access_at=now,
            )
        )
        return
    meta.last_access_at = now
    upsert_sync_meta(meta)
