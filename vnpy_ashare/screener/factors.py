"""Tushare 因子拉取与字段标准化。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.app_db import load_universe_rows
from vnpy_ashare.calendar import last_trading_day
from vnpy_ashare.models import EXCHANGE_TO_SUFFIX
from vnpy_ashare.screener.tushare_client import get_tushare_pro


def ts_code_to_vt_symbol(ts_code: str) -> str | None:
    if "." not in ts_code:
        return None
    code, suffix = ts_code.rsplit(".", 1)
    exchange_map = {"SH": "SSE", "SZ": "SZSE", "BJ": "BSE"}
    exchange = exchange_map.get(suffix.upper())
    if not exchange:
        return None
    return f"{code}.{exchange}"


def vt_symbol_to_ts_code(vt_symbol: str) -> str | None:
    if "." not in vt_symbol:
        return None
    code, exchange = vt_symbol.rsplit(".", 1)
    suffix_map = {"SSE": "SH", "SZSE": "SZ", "BSE": "BJ"}
    suffix = suffix_map.get(exchange.upper())
    if not suffix:
        return None
    return f"{code}.{suffix}"


def merge_quotes_into_fundamentals(
    fund_rows: list[dict[str, Any]],
    quote_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """用 Redis 实时价/换手覆盖 daily_basic 同标的字段。"""
    quote_map = {
        str(row.get("vt_symbol", "")): row
        for row in quote_rows
        if row.get("vt_symbol")
    }
    merged: list[dict[str, Any]] = []
    for row in fund_rows:
        item = dict(row)
        quote = quote_map.get(str(item.get("vt_symbol", "")))
        if quote is None:
            merged.append(item)
            continue
        last_price = quote.get("last_price")
        if last_price:
            item["close"] = float(last_price)
        turnover = quote.get("turnover_rate")
        if turnover:
            item["turnover_rate"] = float(turnover)
        item["source"] = "quote+tushare"
        merged.append(item)
    return merged


def fetch_daily_pct_map(trade_date: str) -> dict[str, float]:
    """拉取指定交易日全市场涨跌幅（供非交易时段涨幅榜）。"""
    pro = get_tushare_pro()
    try:
        frame = pro.daily(trade_date=trade_date, fields="ts_code,pct_chg")
    except Exception:
        return {}
    if frame is None or frame.empty:
        return {}
    return {
        str(record.get("ts_code", "")): _float(record.get("pct_chg"))
        for record in frame.to_dict(orient="records")
        if record.get("ts_code")
    }


def load_ts_code_name_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for symbol, exchange, name in load_universe_rows():
        suffix = EXCHANGE_TO_SUFFIX.get(exchange, "")
        if not suffix:
            continue
        mapping[f"{symbol}.{suffix}"] = name
    return mapping


def _latest_trade_date_str() -> str:
    return last_trading_day().strftime("%Y%m%d")


def fetch_stock_industry_map() -> dict[str, str]:
    """ts_code → 行业名称。"""
    pro = get_tushare_pro()
    try:
        frame = pro.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,industry",
        )
    except Exception:
        return {}
    if frame is None or frame.empty:
        return {}
    mapping: dict[str, str] = {}
    for record in frame.to_dict(orient="records"):
        ts_code = str(record.get("ts_code", "")).strip()
        industry = str(record.get("industry", "") or "").strip()
        if ts_code and industry:
            mapping[ts_code] = industry
    return mapping


def fetch_daily_basic(*, trade_date: str | None = None) -> tuple[list[dict[str, Any]], str]:
    pro = get_tushare_pro()
    trade_date = trade_date or _latest_trade_date_str()
    frame = pro.daily_basic(
        trade_date=trade_date,
        fields=(
            "ts_code,trade_date,close,pe,pe_ttm,pb,ps,total_mv,circ_mv,"
            "turnover_rate,volume_ratio"
        ),
    )
    if frame is None or frame.empty:
        return [], trade_date

    names = load_ts_code_name_map()
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        ts_code = str(record.get("ts_code", ""))
        vt_symbol = ts_code_to_vt_symbol(ts_code)
        if not vt_symbol:
            continue
        symbol = vt_symbol.split(".", 1)[0]
        rows.append(
            {
                "ts_code": ts_code,
                "symbol": symbol,
                "name": names.get(ts_code, ""),
                "vt_symbol": vt_symbol,
                "trade_date": str(record.get("trade_date", trade_date)),
                "close": _float(record.get("close")),
                "pe": _float(record.get("pe")),
                "pe_ttm": _float(record.get("pe_ttm")),
                "pb": _float(record.get("pb")),
                "ps": _float(record.get("ps")),
                "total_mv": _float(record.get("total_mv")),
                "circ_mv": _float(record.get("circ_mv")),
                "turnover_rate": _float(record.get("turnover_rate")),
                "volume_ratio": _float(record.get("volume_ratio")),
            }
        )
    return rows, trade_date


def fetch_moneyflow(*, trade_date: str | None = None) -> tuple[list[dict[str, Any]], str]:
    pro = get_tushare_pro()
    trade_date = trade_date or _latest_trade_date_str()
    frame = pro.moneyflow(
        trade_date=trade_date,
        fields="ts_code,trade_date,net_mf_amount,buy_elg_amount,sell_elg_amount",
    )
    if frame is None or frame.empty:
        return [], trade_date

    names = load_ts_code_name_map()
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        ts_code = str(record.get("ts_code", ""))
        vt_symbol = ts_code_to_vt_symbol(ts_code)
        if not vt_symbol:
            continue
        symbol = vt_symbol.split(".", 1)[0]
        rows.append(
            {
                "ts_code": ts_code,
                "symbol": symbol,
                "name": names.get(ts_code, ""),
                "vt_symbol": vt_symbol,
                "trade_date": str(record.get("trade_date", trade_date)),
                "net_mf_amount": _float(record.get("net_mf_amount")),
                "buy_elg_amount": _float(record.get("buy_elg_amount")),
                "sell_elg_amount": _float(record.get("sell_elg_amount")),
            }
        )
    return rows, trade_date


def _float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0
