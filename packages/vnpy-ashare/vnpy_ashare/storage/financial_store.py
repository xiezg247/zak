"""个股财报本地存储（zak.db）。"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from vnpy_ashare.storage.app_db import init_app_db
from vnpy_common.paths import get_app_db_path

REPORT_TYPES: tuple[str, ...] = (
    "income",
    "balancesheet",
    "cashflow",
    "fina_indicator",
    "express",
    "forecast",
)


@dataclass
class FinancialSyncMeta:
    ts_code: str
    last_sync_at: str
    latest_end_date: str = ""
    latest_ann_date: str = ""
    sync_status: str = "ok"
    error_message: str = ""
    periods_count: int = 0
    last_access_at: str = ""


@dataclass
class FinancialSnapshotRow:
    ts_code: str
    end_date: str
    revenue: float | None = None
    net_income: float | None = None
    operate_profit: float | None = None
    basic_eps: float | None = None
    total_assets: float | None = None
    total_liab: float | None = None
    total_equity: float | None = None
    ocf: float | None = None
    icf: float | None = None
    fcf_flow: float | None = None
    free_cashflow: float | None = None
    roe: float | None = None
    gross_margin: float | None = None
    net_margin: float | None = None
    debt_ratio: float | None = None
    current_ratio: float | None = None
    revenue_yoy: float | None = None
    net_income_yoy: float | None = None
    roe_yoy: float | None = None
    ocf_to_profit: float | None = None
    computed_at: str = ""


def _connect() -> sqlite3.Connection:
    init_app_db()
    conn = sqlite3.connect(get_app_db_path())
    conn.row_factory = sqlite3.Row
    return conn


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
    with _connect() as conn:
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
        conn.commit()


def list_reports(
    ts_code: str,
    report_type: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    with _connect() as conn:
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
    with _connect() as conn:
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
        conn.commit()


def list_snapshots(ts_code: str, *, limit: int = 12) -> list[FinancialSnapshotRow]:
    with _connect() as conn:
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
    with _connect() as conn:
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
    with _connect() as conn:
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
        conn.commit()


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
