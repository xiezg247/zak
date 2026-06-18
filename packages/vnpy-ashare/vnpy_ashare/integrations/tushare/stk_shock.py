"""Tushare 交易所异常波动披露（stk_shock / stk_high_shock）。"""

from __future__ import annotations

import re
from datetime import timedelta

from vnpy_ashare.domain.time.calendar import last_trading_day
from typing import Any, Literal

from pydantic import Field

from vnpy_ashare.domain.symbols.stock import ts_code_to_vt_symbol, vt_symbol_to_ts_code
from vnpy_ashare.integrations.tushare.cache import (
    DATASET_STK_HIGH_SHOCK,
    DATASET_STK_SHOCK,
    DEFAULT_MAX_AGE,
    get_cached_rows,
    set_cached_rows,
)
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.storage.repositories.trade_calendar import previous_open_trading_day
from vnpy_common.domain.base import FrozenModel

ShockType = Literal["shock", "high_shock"]

_DEVIATION_RE = re.compile(r"偏离值累计(?:达到|达)?([0-9]+(?:\.[0-9]+)?)%")
_LIMIT_UP_COUNT_RE = re.compile(r"([0-9]+)\s*次涨停")


class ExchangeRegulatoryRecord(FrozenModel):
    vt_symbol: str = Field(description="vn.py vt_symbol")
    ts_code: str = Field(description="Tushare ts_code")
    trade_date: str = Field(description="公告日期 YYYYMMDD")
    reason: str = Field(default="", description="交易所异常说明")
    period: str = Field(default="", description="异常期间")
    shock_type: ShockType = Field(description="shock=异常波动 high_shock=严重异常波动")


def _recent_open_days(*, count: int) -> list[str]:
    cursor = last_trading_day()
    days: list[str] = []
    for _ in range(max(1, count)):
        days.append(cursor.strftime("%Y%m%d"))
        prev = previous_open_trading_day(cursor)
        if prev is None or prev >= cursor:
            cursor = cursor - timedelta(days=1)
        else:
            cursor = prev
    return days


def _normalize_row(record: dict[str, Any], *, shock_type: ShockType) -> ExchangeRegulatoryRecord | None:
    ts_code = str(record.get("ts_code") or "").strip()
    vt_symbol = ts_code_to_vt_symbol(ts_code)
    if not vt_symbol:
        return None
    trade_date = str(record.get("trade_date") or "").strip()
    if not trade_date:
        return None
    return ExchangeRegulatoryRecord(
        vt_symbol=vt_symbol,
        ts_code=ts_code,
        trade_date=trade_date,
        reason=str(record.get("reason") or "").strip(),
        period=str(record.get("period") or "").strip(),
        shock_type=shock_type,
    )


def _fetch_daily(dataset: str, trade_date: str, *, api_name: str) -> list[dict[str, Any]]:
    cached = get_cached_rows(dataset, trade_date, max_age=DEFAULT_MAX_AGE)
    if cached is not None:
        return cached

    pro = get_tushare_pro()
    api = getattr(pro, api_name)
    try:
        frame = api(trade_date=trade_date, fields="ts_code,trade_date,name,reason,period")
    except Exception:
        return []
    if frame is None or frame.empty:
        set_cached_rows(dataset, trade_date, [])
        return []
    rows = [dict(item) for item in frame.to_dict(orient="records")]
    set_cached_rows(dataset, trade_date, rows)
    return rows


def fetch_stk_shock_daily(trade_date: str) -> list[dict[str, Any]]:
    return _fetch_daily(DATASET_STK_SHOCK, trade_date, api_name="stk_shock")


def fetch_stk_high_shock_daily(trade_date: str) -> list[dict[str, Any]]:
    return _fetch_daily(DATASET_STK_HIGH_SHOCK, trade_date, api_name="stk_high_shock")


def load_recent_exchange_regulatory_for_ts_code(
    ts_code: str,
    *,
    lookback_trading_days: int = 10,
) -> tuple[ExchangeRegulatoryRecord, ...]:
    """按 ts_code 拉取近 N 个交易日的交易所披露记录。"""
    ts_code = str(ts_code or "").strip()
    if not ts_code:
        return ()

    try:
        get_tushare_pro()
    except TushareNotConfiguredError:
        return ()

    records: list[ExchangeRegulatoryRecord] = []
    for trade_date in _recent_open_days(count=lookback_trading_days):
        for row in fetch_stk_high_shock_daily(trade_date):
            if str(row.get("ts_code") or "").strip() != ts_code:
                continue
            item = _normalize_row(row, shock_type="high_shock")
            if item is not None:
                records.append(item)
        for row in fetch_stk_shock_daily(trade_date):
            if str(row.get("ts_code") or "").strip() != ts_code:
                continue
            item = _normalize_row(row, shock_type="shock")
            if item is not None:
                records.append(item)

    records.sort(key=lambda item: (item.trade_date, item.shock_type), reverse=True)
    return tuple(records)


def load_exchange_regulatory_index(
    *,
    lookback_trading_days: int = 10,
) -> dict[str, tuple[ExchangeRegulatoryRecord, ...]]:
    """批量构建 vt_symbol → 近 N 日交易所披露索引（供选股 enrichment）。"""
    try:
        get_tushare_pro()
    except TushareNotConfiguredError:
        return {}

    grouped: dict[str, list[ExchangeRegulatoryRecord]] = {}
    for trade_date in _recent_open_days(count=lookback_trading_days):
        for row in fetch_stk_high_shock_daily(trade_date):
            item = _normalize_row(row, shock_type="high_shock")
            if item is not None:
                grouped.setdefault(item.vt_symbol, []).append(item)
        for row in fetch_stk_shock_daily(trade_date):
            item = _normalize_row(row, shock_type="shock")
            if item is not None:
                grouped.setdefault(item.vt_symbol, []).append(item)

    return {
        vt_symbol: tuple(sorted(items, key=lambda item: (item.trade_date, item.shock_type), reverse=True))
        for vt_symbol, items in grouped.items()
    }


def parse_deviation_pct_from_reason(reason: str) -> float | None:
    match = _DEVIATION_RE.search(reason)
    if match is None:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def summarize_exchange_records(records: tuple[ExchangeRegulatoryRecord, ...]) -> str:
    if not records:
        return ""
    latest = records[0]
    prefix = "严重异常波动" if latest.shock_type == "high_shock" else "异常波动"
    reason = latest.reason or prefix
    if latest.period:
        return f"交易所{prefix}（{latest.period}）：{reason}"
    return f"交易所{prefix}：{reason}"


def load_recent_exchange_regulatory_for_vt_symbol(
    vt_symbol: str,
    *,
    lookback_trading_days: int = 10,
) -> tuple[ExchangeRegulatoryRecord, ...]:
    ts_code = vt_symbol_to_ts_code(vt_symbol)
    if ts_code is None:
        return ()
    return load_recent_exchange_regulatory_for_ts_code(ts_code, lookback_trading_days=lookback_trading_days)
