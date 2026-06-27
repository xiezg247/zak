"""Synthetic / live 基准 P95 上限（CI 与本地回归）。

Synthetic 上限按 ``REFERENCE_SYMBOLS`` 标定并线性缩放；live 上限对齐 ``docs/performance-optimization.md`` SLI，并乘以 ``LIVE_HEADROOM``。
"""

from __future__ import annotations

REFERENCE_SYMBOLS = 5000
HEADROOM = 2.5
LIVE_HEADROOM = 1.5

# 在 REFERENCE_SYMBOLS 下的 P95 上限（毫秒）
SYNTHETIC_P95_LIMITS_MS: dict[str, float] = {
    "quote_snapshot_roundtrip": 80.0,
    "market_rank_sort": 2.0,
    "row_filter_scan": 2.0,
    "hard_filter_polars": 80.0,
    "quote_snapshot_compact_roundtrip": 80.0,
}

# 集成基准 P95 上限（毫秒），名称与 bench/run_hotpaths 输出一致
LIVE_P95_LIMITS_MS: dict[str, float] = {
    "redis.load_market_quote_rows": 800.0,
    "recipe.intraday_multi": 3000.0,
    "radar.leader_pick": 800.0,
}


def scaled_p95_limit_ms(name: str, symbols: int) -> float | None:
    base = SYNTHETIC_P95_LIMITS_MS.get(name)
    if base is None:
        return None
    scale = max(symbols, 1) / REFERENCE_SYMBOLS
    return base * scale * HEADROOM


def live_p95_limit_ms(name: str) -> float | None:
    base = LIVE_P95_LIMITS_MS.get(name)
    if base is None:
        if name.startswith("recipe."):
            return LIVE_P95_LIMITS_MS["recipe.intraday_multi"] * LIVE_HEADROOM
        return None
    return base * LIVE_HEADROOM


def check_synthetic_regression(rows: list[dict[str, float]], *, symbols: int) -> list[str]:
    """返回违规描述列表；空列表表示通过。"""
    violations: list[str] = []
    for row in rows:
        name = str(row.get("name", ""))
        limit = scaled_p95_limit_ms(name, symbols)
        if limit is None:
            continue
        p95 = float(row.get("p95_ms", 0.0))
        if p95 > limit:
            violations.append(f"{name}: p95={p95:.2f}ms > limit={limit:.2f}ms (symbols={symbols})")
    return violations


def check_live_regression(rows: list[dict[str, float]]) -> list[str]:
    violations: list[str] = []
    for row in rows:
        name = str(row.get("name", ""))
        limit = live_p95_limit_ms(name)
        if limit is None:
            continue
        p95 = float(row.get("p95_ms", 0.0))
        if p95 > limit:
            violations.append(f"{name}: p95={p95:.2f}ms > limit={limit:.2f}ms (live)")
    return violations


def redis_bench_ready(*, min_quotes: int = 100) -> bool:
    """Redis 可 ping 且已有全市场行情（供 live bench 探测）。"""
    try:
        from vnpy_ashare.quotes.core.redis_store import get_redis_quote_store

        store = get_redis_quote_store()
        if not store.ping():
            return False
        raw = store.client.get("zak:meta:quote_count")
        if raw is None:
            return False
        return int(raw) >= min_quotes
    except Exception:
        return False
