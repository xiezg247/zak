"""回测运行历史落库（B3）。"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from typing import Any

from pydantic import Field
from sqlalchemy import case, func, select

from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.storage.repository.app import AppUserScopedRepository
from vnpy_common.domain.base import MutableModel
from vnpy_common.storage.compat import DbRow
from vnpy_common.storage.tables import backtest_runs as br

_RUN_COLUMNS = (
    br.c.id,
    br.c.vt_symbol,
    br.c.strategy,
    br.c.interval,
    br.c.start_date,
    br.c.end_date,
    br.c.total_return,
    br.c.max_drawdown,
    br.c.sharpe_ratio,
    br.c.trade_count,
    br.c.source,
    br.c.batch_id,
    br.c.raw_statistics_json,
    br.c.created_at,
)


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


def _row_to_record(row: DbRow) -> BacktestRunRecord:
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


class BacktestRunRepository(AppUserScopedRepository):
    table = br

    def save_backtest_run(
        self,
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
        self.insert_one_for_user(
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
            raw_statistics_json=stats_payload,
            created_at=now,
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

    def list_backtest_runs(self, *, limit: int = 20, vt_symbol: str | None = None) -> list[BacktestRunRecord]:
        extras = (br.c.vt_symbol == vt_symbol,) if vt_symbol else ()
        rows = self.list_for_user(
            *_RUN_COLUMNS,
            extras=extras,
            order_by=(br.c.created_at.desc(),),
            limit=limit,
        )
        return [_row_to_record(row) for row in rows]

    def get_backtest_run(self, run_id: str) -> BacktestRunRecord | None:
        rows = self.list_for_user(*_RUN_COLUMNS, extras=(br.c.id == run_id,), limit=1)
        return _row_to_record(rows[0]) if rows else None

    def list_batch_sessions(self, *, limit: int = 30) -> list[BatchBacktestSession]:
        stmt = (
            select(
                br.c.batch_id,
                func.min(br.c.strategy).label("strategy"),
                func.min(br.c.start_date).label("start_date"),
                func.max(br.c.end_date).label("end_date"),
                func.count().label("row_count"),
                func.sum(
                    case(
                        ((br.c.total_return.isnot(None)) & (br.c.batch_id.isnot(None)), 1),
                        else_=0,
                    )
                ).label("success_count"),
                func.sum(case((br.c.total_return.is_(None), 1), else_=0)).label("error_count"),
                func.min(br.c.source).label("source"),
                func.min(br.c.created_at).label("created_at"),
            )
            .where(self.scope(br.c.batch_id.isnot(None)))
            .group_by(br.c.batch_id)
            .order_by(func.min(br.c.created_at).desc())
            .limit(limit)
        )
        rows = self.fetchall(stmt)
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

    def list_runs_by_batch(self, batch_id: str) -> list[BacktestRunRecord]:
        rows = self.list_for_user(
            *_RUN_COLUMNS,
            extras=(br.c.batch_id == batch_id,),
            order_by=(br.c.total_return.is_(None).desc(), br.c.total_return.desc(), br.c.vt_symbol.asc()),
        )
        return [_row_to_record(row) for row in rows]

    def delete_batch(self, batch_id: str) -> int:
        return self.delete_matching(self.scope(br.c.batch_id == batch_id))


_repo = BacktestRunRepository()


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
    return _repo.save_backtest_run(
        vt_symbol=vt_symbol,
        strategy=strategy,
        interval=interval,
        start=start,
        end=end,
        statistics=statistics,
        source=source,
        batch_id=batch_id,
        total_return=total_return,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe_ratio,
        trade_count=trade_count,
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
    return _repo.list_backtest_runs(limit=limit, vt_symbol=vt_symbol)


def get_backtest_run(run_id: str) -> BacktestRunRecord | None:
    return _repo.get_backtest_run(run_id)


def get_latest_backtest_run(*, vt_symbol: str | None = None) -> BacktestRunRecord | None:
    runs = list_backtest_runs(limit=1, vt_symbol=vt_symbol)
    return runs[0] if runs else None


def list_batch_sessions(*, limit: int = 30) -> list[BatchBacktestSession]:
    return _repo.list_batch_sessions(limit=limit)


def list_runs_by_batch(batch_id: str) -> list[BacktestRunRecord]:
    return _repo.list_runs_by_batch(batch_id)


def delete_batch(batch_id: str) -> int:
    return _repo.delete_batch(batch_id)
