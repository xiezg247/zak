"""形态选股专用日 K 加载（尾部窗口，避免全量扫库）。"""

from __future__ import annotations

import os
from collections import OrderedDict
from datetime import timedelta

from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData

from vnpy_ashare.data.bar_store import get_scope_overview, load_scope_bars, warm_bar_overview_cache
from vnpy_ashare.data.download_concurrency import run_parallel_map
from vnpy_ashare.domain.symbols.stock import StockItem

PATTERN_MIN_BARS = 60
PATTERN_LOOKBACK_BARS = 120
DEFAULT_PATTERN_LOAD_MAX_WORKERS = 4

_BARS_LRU: OrderedDict[tuple[str, Exchange, int], list[BarData]] = OrderedDict()
_BARS_LRU_MAX = max(64, int(os.getenv("ZAK_BARS_TAIL_LRU_SIZE", "512")))


def _bars_lru_get(key: tuple[str, Exchange, int]) -> list[BarData] | None:
    bars = _BARS_LRU.get(key)
    if bars is None:
        return None
    _BARS_LRU.move_to_end(key)
    return bars


def _bars_lru_put(key: tuple[str, Exchange, int], bars: list[BarData]) -> None:
    _BARS_LRU[key] = bars
    _BARS_LRU.move_to_end(key)
    while len(_BARS_LRU) > _BARS_LRU_MAX:
        _BARS_LRU.popitem(last=False)


def clear_daily_bars_lru_cache() -> None:
    """测试 / 日切后清空进程内 tail LRU。"""
    _BARS_LRU.clear()


def pattern_load_max_workers(*, item_count: int) -> int:
    """形态选股 DB 读并发数（PATTERN_LOAD_MAX_WORKERS，默认 4）。"""
    raw = os.getenv("PATTERN_LOAD_MAX_WORKERS", str(DEFAULT_PATTERN_LOAD_MAX_WORKERS)).strip()
    try:
        configured = int(raw)
    except ValueError:
        configured = DEFAULT_PATTERN_LOAD_MAX_WORKERS
    configured = max(1, min(configured, 8))
    return min(configured, item_count)


def load_daily_bars_tail(
    symbol: str,
    exchange: Exchange,
    *,
    lookback_bars: int = PATTERN_LOOKBACK_BARS,
) -> list[BarData]:
    """按 overview 尾部加载日 K，供形态规则使用。"""
    overview = get_scope_overview(symbol, exchange, "daily")
    if overview is None:
        return []

    end = overview.end
    calendar_days = int(lookback_bars * 1.6) + 10
    start = end - timedelta(days=calendar_days)
    if start < overview.start:
        start = overview.start

    bars = load_scope_bars(symbol, exchange, "daily", start, end)
    if len(bars) > lookback_bars:
        return bars[-lookback_bars:]
    return bars


def _dedupe_items(items: list[StockItem]) -> list[StockItem]:
    seen: set[tuple[str, Exchange]] = set()
    unique: list[StockItem] = []
    for item in items:
        key = (item.symbol, item.exchange)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _load_daily_bars_entry(item: StockItem, *, lookback_bars: int) -> tuple[tuple[str, Exchange], list[BarData]]:
    key = (item.symbol, item.exchange)
    cache_key = (item.symbol, item.exchange, lookback_bars)
    cached = _bars_lru_get(cache_key)
    if cached is not None:
        return key, cached
    bars = load_daily_bars_tail(item.symbol, item.exchange, lookback_bars=lookback_bars)
    _bars_lru_put(cache_key, bars)
    return key, bars


def load_daily_bars_batch(
    items: list[StockItem],
    *,
    lookback_bars: int = PATTERN_LOOKBACK_BARS,
    max_workers: int | None = None,
) -> dict[tuple[str, Exchange], list[BarData]]:
    """批量加载形态选股所需日 K（尾部窗口；多 worker 并行读库）。"""
    unique = _dedupe_items(items)
    if not unique:
        return {}

    warm_bar_overview_cache()
    workers = max_workers if max_workers is not None else pattern_load_max_workers(item_count=len(unique))
    if workers <= 1 or len(unique) <= 1:
        return {key: bars for key, bars in (_load_daily_bars_entry(item, lookback_bars=lookback_bars) for item in unique)}

    def worker(item: StockItem) -> tuple[tuple[str, Exchange], list[BarData]]:
        return _load_daily_bars_entry(item, lookback_bars=lookback_bars)

    pairs = run_parallel_map(unique, worker, max_workers=workers)
    return dict(pairs)
