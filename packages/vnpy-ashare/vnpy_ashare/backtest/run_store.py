"""回测运行历史落库（B3）。"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from typing import Any

from pydantic import Field

from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.storage.cache.sqlite_session import sqlite_cache_session
from vnpy_common.domain.base import MutableModel
from vnpy_common.paths import get_app_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS backtest_runs (
    id TEXT PRIMARY KEY,
    vt_symbol TEXT NOT NULL,
    strategy TEXT NOT NULL,
    interval TEXT NOT NULL DEFAULT 'd',
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    total_return REAL,
    max_drawdown REAL,
    sharpe_ratio REAL,
    trade_count INTEGER,
    source TEXT NOT NULL DEFAULT 'single',
    batch_id TEXT,
    raw_statistics_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_created ON backtest_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_batch ON backtest_runs(batch_id);
"""


class BatchBacktestSession(MutableModel):
    batch_id: str = Field(description="批量回测批次 ID")
    strategy: str = Field(description="策略类名")
    start_date: str = Field(description="回测起始日")
    end_date: str = Field(description="回测结束日")
    row_count: int = Field(description="总行数")
    success_count: int = Field(description="成功数")
    error_count: int = Field(description="失败数")
    source: str = Field(description="来源标识")
    created_at: str = Field(description="创建时间")


class BacktestRunRecord(MutableModel):
    id: str = Field(description="记录主键")
    vt_symbol: str = Field(description="VeighNa 合约代码")
    strategy: str = Field(description="策略类名")
    interval: str = Field(description="K 线周期")
    start_date: str = Field(description="回测起始日")
    end_date: str = Field(description="回测结束日")
    total_return: float | None = Field(description="总收益率")
    max_drawdown: float | None = Field(description="最大回撤")
    sharpe_ratio: float | None = Field(description="夏普比率")
    trade_count: int | None = Field(description="成交笔数")
    source: str = Field(description="来源：single/batch")
    batch_id: str | None = Field(description="批量回测批次 ID")
    raw_statistics: dict[str, Any] = Field(description="原始统计 JSON")
    created_at: str = Field(description="创建时间")

    def to_summary_dict(self) -> dict[str, Any]:
        """与 context_store BacktestSummary（dump_python）对齐。"""
        return {
            "strategy": self.strategy,
            "vt_symbol": self.vt_symbol,
            "interval": self.interval,
            "start": self.start_date,
            "end": self.end_date,
            "statistics": dict(self.raw_statistics),
            "total_return": self.total_return,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "trade_count": self.trade_count,
            "source": self.source,
            "created_at": self.created_at,
        }


def _connect():
    return sqlite_cache_session(get_app_db_path(), _SCHEMA)


def _now() -> str:
    return format_china_datetime()


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        text = str(value).replace("%", "").strip()
        return float(text)
    except (TypeError, ValueError):
        return None


def _extract_metrics(statistics: dict[str, Any]) -> tuple[float | None, float | None, float | None, int | None]:
    total_return = _to_float(statistics.get("total_return"))
    max_drawdown = _to_float(statistics.get("max_drawdown"))
    sharpe_ratio = _to_float(statistics.get("sharpe_ratio"))
    trade_count_raw = statistics.get("total_trade_count")
    trade_count = int(trade_count_raw) if trade_count_raw is not None else None
    return total_return, max_drawdown, sharpe_ratio, trade_count


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=_json_default)


def save_backtest_run(
    *,
    vt_symbol: str,
    strategy: str,
    interval: str,
    start: str,
    end: str,
    statistics: dict[str, Any] | None = None,
    source: str = "single",
    batch_id: str | None = None,
    total_return: float | None = None,
    max_drawdown: float | None = None,
    sharpe_ratio: float | None = None,
    trade_count: int | None = None,
) -> BacktestRunRecord:
    stats = dict(statistics or {})
    if total_return is None and max_drawdown is None:
        extracted = _extract_metrics(stats)
        total_return, max_drawdown, sharpe_ratio, trade_count = extracted
    elif trade_count is None:
        _, _, _, trade_count = _extract_metrics(stats)

    run_id = uuid.uuid4().hex
    now = _now()
    stats_payload = _json_dumps(stats)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO backtest_runs
            (id, vt_symbol, strategy, interval, start_date, end_date,
             total_return, max_drawdown, sharpe_ratio, trade_count,
             source, batch_id, raw_statistics_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                vt_symbol,
                strategy,
                interval,
                start[:10],
                end[:10],
                total_return,
                max_drawdown,
                sharpe_ratio,
                trade_count,
                source,
                batch_id,
                stats_payload,
                now,
            ),
        )
    return BacktestRunRecord(
        id=run_id,
        vt_symbol=vt_symbol,
        strategy=strategy,
        interval=interval,
        start_date=start[:10],
        end_date=end[:10],
        total_return=total_return,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe_ratio,
        trade_count=trade_count,
        source=source,
        batch_id=batch_id,
        raw_statistics=stats,
        created_at=now,
    )


def save_backtest_summary_dict(summary: dict[str, Any], *, source: str = "single") -> BacktestRunRecord:
    """从 BacktestSummary（dump_python）写入。"""
    return save_backtest_run(
        vt_symbol=str(summary.get("vt_symbol", "")),
        strategy=str(summary.get("strategy", "")),
        interval=str(summary.get("interval", "d")),
        start=str(summary.get("start", "")),
        end=str(summary.get("end", "")),
        statistics=dict(summary.get("statistics") or {}),
        source=source,
    )


def list_backtest_runs(*, limit: int = 20, vt_symbol: str | None = None) -> list[BacktestRunRecord]:
    query = """
        SELECT id, vt_symbol, strategy, interval, start_date, end_date,
               total_return, max_drawdown, sharpe_ratio, trade_count,
               source, batch_id, raw_statistics_json, created_at
        FROM backtest_runs
    """
    params: list[Any] = []
    if vt_symbol:
        query += " WHERE vt_symbol=?"
        params.append(vt_symbol)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_record(row) for row in rows]


def get_backtest_run(run_id: str) -> BacktestRunRecord | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, vt_symbol, strategy, interval, start_date, end_date,
                   total_return, max_drawdown, sharpe_ratio, trade_count,
                   source, batch_id, raw_statistics_json, created_at
            FROM backtest_runs WHERE id=?
            """,
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_record(row)


def get_latest_backtest_run(*, vt_symbol: str | None = None) -> BacktestRunRecord | None:
    runs = list_backtest_runs(limit=1, vt_symbol=vt_symbol)
    return runs[0] if runs else None


def list_batch_sessions(*, limit: int = 30) -> list[BatchBacktestSession]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                batch_id,
                strategy,
                MIN(start_date) AS start_date,
                MAX(end_date) AS end_date,
                COUNT(*) AS row_count,
                SUM(CASE WHEN total_return IS NOT NULL AND batch_id IS NOT NULL THEN 1 ELSE 0 END) AS success_count,
                SUM(CASE WHEN total_return IS NULL THEN 1 ELSE 0 END) AS error_count,
                MIN(source) AS source,
                MIN(created_at) AS created_at
            FROM backtest_runs
            WHERE batch_id IS NOT NULL
            GROUP BY batch_id
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        BatchBacktestSession(
            batch_id=str(row["batch_id"]),
            strategy=str(row["strategy"]),
            start_date=str(row["start_date"]),
            end_date=str(row["end_date"]),
            row_count=int(row["row_count"]),
            success_count=int(row["success_count"] or 0),
            error_count=int(row["error_count"] or 0),
            source=str(row["source"]),
            created_at=str(row["created_at"]),
        )
        for row in rows
    ]


def list_runs_by_batch(batch_id: str) -> list[BacktestRunRecord]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, vt_symbol, strategy, interval, start_date, end_date,
                   total_return, max_drawdown, sharpe_ratio, trade_count,
                   source, batch_id, raw_statistics_json, created_at
            FROM backtest_runs
            WHERE batch_id=?
            ORDER BY (total_return IS NULL), total_return DESC, vt_symbol ASC
            """,
            (batch_id,),
        ).fetchall()
    return [_row_to_record(row) for row in rows]


def delete_batch(batch_id: str) -> int:
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM backtest_runs WHERE batch_id=?", (batch_id,))
        return int(cursor.rowcount or 0)


def _row_to_record(row: sqlite3.Row) -> BacktestRunRecord:
    return BacktestRunRecord(
        id=str(row["id"]),
        vt_symbol=str(row["vt_symbol"]),
        strategy=str(row["strategy"]),
        interval=str(row["interval"]),
        start_date=str(row["start_date"]),
        end_date=str(row["end_date"]),
        total_return=row["total_return"],
        max_drawdown=row["max_drawdown"],
        sharpe_ratio=row["sharpe_ratio"],
        trade_count=row["trade_count"],
        source=str(row["source"]),
        batch_id=str(row["batch_id"]) if row["batch_id"] else None,
        raw_statistics=json.loads(str(row["raw_statistics_json"] or "{}")),
        created_at=str(row["created_at"]),
    )
