"""行情快照合并 Tushare 日频因子（量比、主力净流入）。"""

from __future__ import annotations

import time

from vnpy_ashare.domain.symbols import parse_stock_symbol, parse_tickflow_symbol
from vnpy_ashare.quotes.core.snapshot import QuoteSnapshot
from vnpy_ashare.quotes.market.market_breadth import LIMIT_UP_PCT
from vnpy_ashare.screener.data.data_source import (
    fetch_daily_basic_with_fallback,
    fetch_limit_list_with_fallback,
    fetch_moneyflow_with_fallback,
)

_FACTOR_MAPS_CACHE: tuple[dict[str, float], dict[str, float], float] | None = None
_LIMIT_TIMES_MAP_CACHE: tuple[dict[str, float], float] | None = None
_FACTOR_MAPS_TTL_SEC = 300.0


def _apply_limit_times(
    quote: QuoteSnapshot,
    *,
    tf_symbol: str,
    limit_times_map: dict[str, float],
) -> None:
    if quote.limit_times >= 1:
        return
    boards = limit_times_map.get(tf_symbol)
    if boards is not None and boards >= 1:
        quote.limit_times = boards
    elif quote.change_pct >= LIMIT_UP_PCT:
        quote.limit_times = 1.0


def get_cached_limit_times_map(*, force_refresh: bool = False) -> dict[str, float]:
    """带 TTL 的连板 map 缓存。"""
    global _LIMIT_TIMES_MAP_CACHE
    now = time.monotonic()
    if not force_refresh and _LIMIT_TIMES_MAP_CACHE is not None:
        limit_times_map, cached_at = _LIMIT_TIMES_MAP_CACHE
        if now - cached_at < _FACTOR_MAPS_TTL_SEC:
            return limit_times_map
    try:
        limit_times_map = load_limit_times_map_by_tickflow()
    except Exception:
        limit_times_map = {}
    _LIMIT_TIMES_MAP_CACHE = (limit_times_map, now)
    return limit_times_map


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


def get_cached_tushare_factor_maps(*, force_refresh: bool = False) -> tuple[dict[str, float], dict[str, float]]:
    """带 TTL 的因子 map 缓存，供 Redis 读取路径补全缺失字段。"""
    global _FACTOR_MAPS_CACHE
    now = time.monotonic()
    if not force_refresh and _FACTOR_MAPS_CACHE is not None:
        ratio_map, mf_map, cached_at = _FACTOR_MAPS_CACHE
        if now - cached_at < _FACTOR_MAPS_TTL_SEC:
            return ratio_map, mf_map
    try:
        ratio_map, mf_map = load_tushare_factor_maps_by_tickflow()
    except Exception:
        ratio_map, mf_map = {}, {}
    _FACTOR_MAPS_CACHE = (ratio_map, mf_map, now)
    return ratio_map, mf_map


def _quote_needs_tushare_factors(quote: QuoteSnapshot) -> bool:
    return quote.volume_ratio <= 0 or quote.net_mf_amount == 0 or quote.limit_times < 1


def fill_missing_tushare_factors(quotes: dict[str, QuoteSnapshot]) -> None:
    """Redis 快照缺 Tushare 日频因子时，从本地缓存补全（不覆盖已有值）。"""
    if not quotes:
        return
    if not any(_quote_needs_tushare_factors(quote) for quote in quotes.values()):
        return

    ratio_map, mf_map = get_cached_tushare_factor_maps()
    limit_times_map: dict[str, float] = {}
    needs_board_lookup = any(quote.limit_times < 1 and quote.change_pct >= LIMIT_UP_PCT for quote in quotes.values())
    if needs_board_lookup:
        limit_times_map = get_cached_limit_times_map()

    for tf_symbol, quote in quotes.items():
        if quote.volume_ratio <= 0:
            ratio = ratio_map.get(tf_symbol)
            if ratio is not None and ratio > 0:
                quote.volume_ratio = ratio
        if quote.net_mf_amount == 0:
            mf_amount = mf_map.get(tf_symbol)
            if mf_amount is not None and mf_amount != 0:
                quote.net_mf_amount = mf_amount
        if quote.limit_times < 1 and (needs_board_lookup or quote.change_pct >= LIMIT_UP_PCT):
            _apply_limit_times(quote, tf_symbol=tf_symbol, limit_times_map=limit_times_map)


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
    global _FACTOR_MAPS_CACHE
    try:
        ratio_map, mf_map = load_tushare_factor_maps_by_tickflow()
        _FACTOR_MAPS_CACHE = (ratio_map, mf_map, time.monotonic())
    except Exception:
        ratio_map, mf_map = {}, {}

    try:
        limit_times_map = load_limit_times_map_by_tickflow()
        _LIMIT_TIMES_MAP_CACHE = (limit_times_map, time.monotonic())
    except Exception:
        limit_times_map = {}

    for tf_symbol, quote in quotes.items():
        ratio = ratio_map.get(tf_symbol)
        if ratio is not None and ratio > 0:
            quote.volume_ratio = ratio
        mf_amount = mf_map.get(tf_symbol)
        if mf_amount is not None and mf_amount != 0:
            quote.net_mf_amount = mf_amount
        _apply_limit_times(quote, tf_symbol=tf_symbol, limit_times_map=limit_times_map)
