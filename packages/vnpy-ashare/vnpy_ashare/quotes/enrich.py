"""行情快照合并 Tushare 日频因子（量比、主力净流入）。"""

from __future__ import annotations

from vnpy_ashare.domain.symbols import parse_stock_symbol, parse_tickflow_symbol
from vnpy_ashare.quotes.market_breadth import LIMIT_UP_PCT
from vnpy_ashare.quotes.snapshot import QuoteSnapshot
from vnpy_ashare.screener.data.data_source import (
    fetch_daily_basic_with_fallback,
    fetch_limit_list_with_fallback,
    fetch_moneyflow_with_fallback,
)


def load_tushare_factor_maps_by_tickflow() -> tuple[dict[str, float], dict[str, float]]:
    """按 TickFlow symbol 索引 Tushare 量比与主力净流入（万元）。"""
    ratio_map: dict[str, float] = {}
    basic_rows, _ = fetch_daily_basic_with_fallback()
    for row in basic_rows:
        vt_symbol = str(row.get("vt_symbol") or "").strip()
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            continue
        ratio = float(row.get("volume_ratio") or 0)
        if ratio > 0:
            ratio_map[item.tickflow_symbol] = ratio

    mf_map: dict[str, float] = {}
    mf_rows, _ = fetch_moneyflow_with_fallback()
    for row in mf_rows:
        vt_symbol = str(row.get("vt_symbol") or "").strip()
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            continue
        amount = float(row.get("net_mf_amount") or 0)
        if amount != 0:
            mf_map[item.tickflow_symbol] = amount

    return ratio_map, mf_map


def load_limit_times_map_by_tickflow() -> dict[str, float]:
    """按 TickFlow symbol 索引 Tushare 涨停连板数。"""
    rows, _ = fetch_limit_list_with_fallback(limit_type="U")
    result: dict[str, float] = {}
    for row in rows:
        if str(row.get("limit") or "") != "U":
            continue
        boards = float(row.get("limit_times") or 0)
        if boards < 1:
            continue
        ts_code = str(row.get("ts_code") or "").strip()
        item = parse_tickflow_symbol(ts_code) if ts_code else None
        if item is None:
            vt_symbol = str(row.get("vt_symbol") or "").strip()
            item = parse_stock_symbol(vt_symbol) if vt_symbol else None
        if item is None:
            continue
        result[item.tickflow_symbol] = boards
    return result


def enrich_quotes_with_tushare_factors(quotes: dict[str, QuoteSnapshot]) -> None:
    """就地合并 Tushare 因子；Tushare 不可用时静默跳过。"""
    if not quotes:
        return
    try:
        ratio_map, mf_map = load_tushare_factor_maps_by_tickflow()
    except Exception:
        ratio_map, mf_map = {}, {}

    try:
        limit_times_map = load_limit_times_map_by_tickflow()
    except Exception:
        limit_times_map = {}

    for tf_symbol, quote in quotes.items():
        ratio = ratio_map.get(tf_symbol)
        if ratio is not None and ratio > 0:
            quote.volume_ratio = ratio
        mf_amount = mf_map.get(tf_symbol)
        if mf_amount is not None and mf_amount != 0:
            quote.net_mf_amount = mf_amount
        boards = limit_times_map.get(tf_symbol)
        if boards is not None and boards >= 1:
            quote.limit_times = boards
        elif quote.change_pct >= LIMIT_UP_PCT:
            quote.limit_times = max(quote.limit_times, 1.0)
