"""连板数 map 进程内 TTL 缓存（打破 enrich ↔ data_source 循环）。"""

from __future__ import annotations

import time

from vnpy_ashare.domain.symbols import parse_stock_symbol, parse_tickflow_symbol
from vnpy_ashare.integrations.tushare.limit_list_fallback import fetch_limit_list_with_fallback

_FACTOR_MAPS_TTL_SEC = 300.0
_LIMIT_TIMES_MAP_CACHE: tuple[dict[str, float], float] | None = None


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


def store_limit_times_map_cache(limit_times_map: dict[str, float]) -> None:
    """由 enrich 批量写入后同步缓存。"""
    global _LIMIT_TIMES_MAP_CACHE
    _LIMIT_TIMES_MAP_CACHE = (dict(limit_times_map), time.monotonic())


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
