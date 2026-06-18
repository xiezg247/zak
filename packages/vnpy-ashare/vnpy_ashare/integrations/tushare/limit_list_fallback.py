"""涨跌停列表按交易日回退（无 screener 包依赖）。"""

from __future__ import annotations

from datetime import date
from typing import Any

from vnpy_ashare.domain.time.trade_dates import DEFAULT_LOOKBACK_DAYS, iter_trade_date_strs
from vnpy_ashare.integrations.tushare.factors import fetch_limit_list_d


def fetch_limit_list_with_fallback(
    *,
    max_lookback: int = DEFAULT_LOOKBACK_DAYS,
    start: date | None = None,
    limit_type: str | None = "U",
) -> tuple[list[dict[str, Any]], str]:
    """按交易日回退拉取涨跌停列表（默认涨停）。"""
    last_tried = ""
    for trade_date in iter_trade_date_strs(max_lookback=max_lookback, start=start):
        last_tried = trade_date
        rows, _ = fetch_limit_list_d(trade_date=trade_date, limit_type=limit_type)
        if rows:
            return rows, trade_date
    return [], last_tried


def load_limit_list_first_time_map() -> dict[str, str]:
    """vt_symbol → first_time（Tushare limit_list_d，缺失则空）。"""
    rows, _ = fetch_limit_list_with_fallback(limit_type="U")
    result: dict[str, str] = {}
    for row in rows:
        vt_symbol = str(row.get("vt_symbol") or "").strip()
        if not vt_symbol:
            continue
        first_time = str(row.get("first_time") or "").strip()
        if first_time:
            result[vt_symbol] = first_time
    return result


def load_limit_list_seal_map() -> dict[str, dict[str, Any]]:
    """vt_symbol → 封单字段（fd_amount / open_times / strth）。"""
    rows, _ = fetch_limit_list_with_fallback(limit_type="U")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        vt_symbol = str(row.get("vt_symbol") or "").strip()
        if not vt_symbol:
            continue
        payload: dict[str, Any] = {}
        if row.get("fd_amount") is not None:
            payload["fd_amount"] = row["fd_amount"]
        if row.get("open_times") is not None:
            payload["open_times"] = row["open_times"]
        if row.get("strth") is not None:
            payload["strth"] = row["strth"]
        if payload:
            result[vt_symbol] = payload
    return result
