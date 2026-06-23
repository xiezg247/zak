"""Tushare 日频因子按交易日回退（无 screener 包依赖）。"""

from __future__ import annotations

from datetime import date
from typing import Any

from vnpy_ashare.domain.time.calendar import last_trading_day
from vnpy_ashare.domain.time.trade_dates import DEFAULT_LOOKBACK_DAYS, iter_trade_date_strs
from vnpy_ashare.integrations.tushare.factors import fetch_daily_basic, fetch_moneyflow

_LAST_SUCCESS_TRADE_DATE: dict[str, str] = {}


def resolve_latest_factor_trade_date(
    *,
    max_lookback: int = DEFAULT_LOOKBACK_DAYS,
    start: date | None = None,
) -> str:
    """返回本地/远端可用的最近 Tushare 日频因子交易日（YYYYMMDD）。"""
    _rows, trade_date = fetch_daily_basic_with_fallback(max_lookback=max_lookback, start=start)
    if trade_date:
        return trade_date
    return last_trading_day(on_or_before=start).strftime("%Y%m%d")


def fetch_daily_basic_with_fallback(
    *,
    max_lookback: int = DEFAULT_LOOKBACK_DAYS,
    start: date | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """按交易日回退拉取 daily_basic，直到有数据或耗尽 lookback。"""
    last_tried = ""
    for trade_date in iter_trade_date_strs(max_lookback=max_lookback, start=start):
        last_tried = trade_date
        rows, _ = fetch_daily_basic(trade_date=trade_date)
        if rows:
            _LAST_SUCCESS_TRADE_DATE["daily_basic"] = trade_date
            return rows, trade_date
    return [], last_tried


def fetch_moneyflow_with_fallback(
    *,
    max_lookback: int = DEFAULT_LOOKBACK_DAYS,
    start: date | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """按交易日回退拉取 moneyflow，直到有数据或耗尽 lookback。"""
    last_tried = ""
    for trade_date in iter_trade_date_strs(max_lookback=max_lookback, start=start):
        last_tried = trade_date
        rows, _ = fetch_moneyflow(trade_date=trade_date)
        if rows:
            _LAST_SUCCESS_TRADE_DATE["moneyflow"] = trade_date
            return rows, trade_date
    return [], last_tried
