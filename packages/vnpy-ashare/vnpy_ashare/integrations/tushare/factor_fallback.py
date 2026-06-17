"""Tushare 日频因子按交易日回退（无 screener 包依赖）。"""

from __future__ import annotations

from datetime import date
from typing import Any

from vnpy_ashare.domain.trade_dates import DEFAULT_LOOKBACK_DAYS, iter_trade_date_strs
from vnpy_ashare.integrations.tushare.factors import fetch_daily_basic, fetch_moneyflow

_LAST_SUCCESS_TRADE_DATE: dict[str, str] = {}


def fetch_daily_basic_with_fallback(
    *,
    max_lookback: int = DEFAULT_LOOKBACK_DAYS,
    start: date | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """按交易日回退拉取 daily_basic，直到有数据或耗尽 lookback。"""
    if start is None and max_lookback == DEFAULT_LOOKBACK_DAYS:
        hinted = _LAST_SUCCESS_TRADE_DATE.get("daily_basic")
        if hinted:
            rows, _ = fetch_daily_basic(trade_date=hinted)
            if rows:
                return rows, hinted

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
    if start is None and max_lookback == DEFAULT_LOOKBACK_DAYS:
        hinted = _LAST_SUCCESS_TRADE_DATE.get("moneyflow")
        if hinted:
            rows, _ = fetch_moneyflow(trade_date=hinted)
            if rows:
                return rows, hinted

    last_tried = ""
    for trade_date in iter_trade_date_strs(max_lookback=max_lookback, start=start):
        last_tried = trade_date
        rows, _ = fetch_moneyflow(trade_date=trade_date)
        if rows:
            _LAST_SUCCESS_TRADE_DATE["moneyflow"] = trade_date
            return rows, trade_date
    return [], last_tried
