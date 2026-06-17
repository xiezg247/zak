"""行情快照合并 Tushare 日频因子（量比、主力净流入）。"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import TYPE_CHECKING

from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.quotes.core.limit_times_cache import (
    get_cached_limit_times_map,
    load_limit_times_map_by_tickflow,
    store_limit_times_map_cache,
)
from vnpy_ashare.quotes.core.snapshot import QuoteSnapshot
from vnpy_ashare.quotes.market.market_breadth import LIMIT_UP_PCT
from vnpy_ashare.quotes.misc.volume_ratio import fill_intraday_volume_ratios
from vnpy_ashare.integrations.tushare.factor_fallback import fetch_daily_basic_with_fallback, fetch_moneyflow_with_fallback

if TYPE_CHECKING:
    from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore

_FACTOR_MAPS_CACHE: tuple[dict[str, float], dict[str, float], float] | None = None
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


def merge_quote_snapshot(existing: QuoteSnapshot, incoming: QuoteSnapshot) -> QuoteSnapshot:
    """合并快照：实时字段用 incoming，日频因子在 incoming 缺失时保留 existing。"""
    return replace(
        incoming,
        name=incoming.name or existing.name,
        turnover_rate=incoming.turnover_rate if incoming.turnover_rate > 0 else existing.turnover_rate,
        volume_ratio=incoming.volume_ratio if incoming.volume_ratio > 0 else existing.volume_ratio,
        net_mf_amount=incoming.net_mf_amount if incoming.net_mf_amount != 0 else existing.net_mf_amount,
        change_speed_5m=incoming.change_speed_5m if incoming.change_speed_5m != 0 else existing.change_speed_5m,
        limit_times=incoming.limit_times if incoming.limit_times >= 1 else existing.limit_times,
    )


def merge_quote_maps_into(target: dict[str, QuoteSnapshot], incoming: dict[str, QuoteSnapshot]) -> None:
    """就地合并行情字典，避免刷新用空因子覆盖已有值。"""
    for key, new_quote in incoming.items():
        old = target.get(key)
        if old is None:
            target[key] = new_quote
        else:
            target[key] = merge_quote_snapshot(old, new_quote)


def backfill_rank_scores_from_zset(store: RedisQuoteStore, quotes: dict[str, QuoteSnapshot]) -> None:
    """HASH 缺榜字段时，用 Redis ZSET score 回填（解决榜序与快照不一致）。"""
    if not quotes:
        return

    tf_symbols = list(quotes.keys())
    volume_needs = [sym for sym in tf_symbols if quotes[sym].volume_ratio <= 0]
    if volume_needs:
        for sym, score in store.get_rank_scores("volume_ratio", volume_needs).items():
            quote = quotes.get(sym)
            if quote is not None and score > 0 and quote.volume_ratio <= 0:
                quote.volume_ratio = score

    mf_needs = [sym for sym in tf_symbols if quotes[sym].net_mf_amount == 0]
    if mf_needs:
        for sym, score in store.get_rank_scores("net_mf_amount", mf_needs).items():
            quote = quotes.get(sym)
            if quote is not None and score != 0 and quote.net_mf_amount == 0:
                quote.net_mf_amount = score

    speed_needs = [sym for sym in tf_symbols if quotes[sym].change_speed_5m == 0]
    if speed_needs:
        for sym, score in store.get_rank_scores("change_speed_5m", speed_needs).items():
            quote = quotes.get(sym)
            if quote is not None and score != 0 and quote.change_speed_5m == 0:
                quote.change_speed_5m = score

    limit_needs = [sym for sym in tf_symbols if quotes[sym].limit_times < 1]
    if limit_needs:
        for sym, score in store.get_rank_scores("limit_times", limit_needs).items():
            quote = quotes.get(sym)
            if quote is not None and score >= 1 and quote.limit_times < 1:
                quote.limit_times = score


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
    fill_intraday_volume_ratios(quotes)


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
        store_limit_times_map_cache(limit_times_map)
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
    fill_intraday_volume_ratios(quotes)
