"""Tushare 龙虎榜（top_list / top_inst）。"""

from __future__ import annotations

from typing import Any, cast

from vnpy_ashare.domain.core.numbers import safe_float
from vnpy_ashare.domain.time.trade_dates import iter_trade_date_strs
from vnpy_ashare.integrations.tushare.client import get_tushare_pro


def _records(frame) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    return cast(list[dict[str, Any]], frame.to_dict(orient="records"))


def fetch_top_list_for_date(*, trade_date: str, ts_code: str) -> list[dict[str, Any]]:
    """单日单票龙虎榜统计。"""
    ts_code = str(ts_code or "").strip()
    trade_date = str(trade_date or "").strip()
    if not ts_code or not trade_date:
        return []
    try:
        pro = get_tushare_pro()
        frame = pro.top_list(
            trade_date=trade_date,
            ts_code=ts_code,
            fields="trade_date,ts_code,name,close,pct_change,turnover_rate,amount,l_buy,l_sell,net_amount,net_rate,reason",
        )
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for record in _records(frame):
        rows.append(
            {
                "trade_date": str(record.get("trade_date") or trade_date),
                "ts_code": str(record.get("ts_code") or ts_code),
                "name": str(record.get("name") or ""),
                "close": safe_float(record.get("close"), default=float("nan")),
                "pct_change": safe_float(record.get("pct_change"), default=float("nan")),
                "turnover_rate": safe_float(record.get("turnover_rate"), default=float("nan")),
                "amount": safe_float(record.get("amount"), default=float("nan")),
                "l_buy": safe_float(record.get("l_buy"), default=float("nan")),
                "l_sell": safe_float(record.get("l_sell"), default=float("nan")),
                "net_amount": safe_float(record.get("net_amount"), default=float("nan")),
                "net_rate": safe_float(record.get("net_rate"), default=float("nan")),
                "reason": str(record.get("reason") or "").strip(),
            }
        )
        for key in ("close", "pct_change", "turnover_rate", "amount", "l_buy", "l_sell", "net_amount", "net_rate"):
            value = rows[-1].get(key)
            if isinstance(value, float) and value != value:
                rows[-1][key] = None
    return rows


def fetch_top_list_history(
    ts_code: str,
    *,
    max_days: int = 60,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """近 N 个交易日龙虎榜历史上榜记录（倒序）。"""
    ts_code = str(ts_code or "").strip()
    if not ts_code:
        return []

    history: list[dict[str, Any]] = []
    for trade_date in iter_trade_date_strs(max_lookback=max(1, max_days)):
        rows = fetch_top_list_for_date(trade_date=trade_date, ts_code=ts_code)
        if rows:
            history.extend(rows)
        if len(history) >= limit:
            break
    history.sort(key=lambda row: str(row.get("trade_date") or ""), reverse=True)
    return history[:limit]


def fetch_top_inst_for_date(*, trade_date: str, ts_code: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """单日单票龙虎榜机构席位（买入前五 / 卖出前五）。"""
    ts_code = str(ts_code or "").strip()
    trade_date = str(trade_date or "").strip()
    if not ts_code or not trade_date:
        return [], []

    try:
        pro = get_tushare_pro()
        frame = pro.top_inst(
            trade_date=trade_date,
            ts_code=ts_code,
            fields="trade_date,ts_code,exalter,side,buy,buy_rate,sell,sell_rate,net_buy,reason",
        )
    except Exception:
        return [], []

    buys: list[dict[str, Any]] = []
    sells: list[dict[str, Any]] = []
    for record in _records(frame):
        side = str(record.get("side") or "").strip()
        row = {
            "trade_date": str(record.get("trade_date") or trade_date),
            "ts_code": str(record.get("ts_code") or ts_code),
            "exalter": str(record.get("exalter") or "").strip(),
            "side": side,
            "buy": safe_float(record.get("buy"), default=float("nan")),
            "sell": safe_float(record.get("sell"), default=float("nan")),
            "net_buy": safe_float(record.get("net_buy"), default=float("nan")),
            "reason": str(record.get("reason") or "").strip(),
        }
        for key in ("buy", "sell", "net_buy"):
            value = row.get(key)
            if isinstance(value, float) and value != value:
                row[key] = None
        if side == "0":
            buys.append(row)
        elif side == "1":
            sells.append(row)
    buys.sort(key=lambda item: item.get("buy") or 0, reverse=True)
    sells.sort(key=lambda item: item.get("sell") or 0, reverse=True)
    return buys[:5], sells[:5]
