#!/usr/bin/env python3
"""zak 热路径性能基准（Phase 0）。

Synthetic 模式不依赖 Redis / PostgreSQL，可在 CI 或离线环境运行::

    uv run python bench/run_hotpaths.py
    uv run python bench/run_hotpaths.py --symbols 5000 --rounds 10

集成模式（需 Redis 已有行情）::

    uv run python bench/run_hotpaths.py --integration redis
    uv run python bench/run_hotpaths.py --integration recipe --recipe intraday_multi
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bench.fixtures import make_synthetic_quote_rows, make_synthetic_quote_snapshots  # noqa: E402
from vnpy_ashare.domain.market.quote_row import QuoteRow  # noqa: E402
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot  # noqa: E402


def _bench(name: str, fn: Callable[[], object], *, rounds: int) -> dict[str, float]:
    timings: list[float] = []
    result = None
    for _ in range(rounds):
        start = time.perf_counter()
        result = fn()
        timings.append((time.perf_counter() - start) * 1000)
    return {
        "name": name,
        "rounds": float(rounds),
        "p50_ms": statistics.median(timings),
        "p95_ms": sorted(timings)[max(0, int(rounds * 0.95) - 1)],
        "min_ms": min(timings),
        "max_ms": max(timings),
        "result_size": float(len(result)) if hasattr(result, "__len__") else 0.0,
    }


def bench_quote_snapshot_roundtrip(*, symbols: int, rounds: int) -> dict[str, float]:
    quotes = make_synthetic_quote_snapshots(symbols)

    def run() -> list[QuoteSnapshot | None]:
        parsed: list[QuoteSnapshot | None] = []
        for quote in quotes.values():
            parsed.append(QuoteSnapshot.from_redis_hash(quote.to_redis_hash()))
        return parsed

    return _bench("quote_snapshot_roundtrip", run, rounds=rounds)


def bench_market_rank_sort(*, symbols: int, rounds: int) -> dict[str, float]:
    rows = make_synthetic_quote_rows(symbols)

    def run() -> list[QuoteRow]:
        return sorted(rows, key=lambda row: row.change_pct, reverse=True)[:200]

    return _bench("market_rank_sort", run, rounds=rounds)


def bench_row_filter_scan(*, symbols: int, rounds: int) -> dict[str, float]:
    """模拟选股硬过滤的 Python 行扫描（不访问 PG / Redis）。"""
    rows = make_synthetic_quote_rows(symbols)
    min_amount = 30_000_000.0

    def run() -> list[QuoteRow]:
        kept: list[QuoteRow] = []
        for row in rows:
            if row.name.startswith("ST"):
                continue
            if row.amount < min_amount:
                continue
            if row.change_pct <= -9.9 or row.change_pct >= 9.9:
                continue
            kept.append(row)
        return kept

    return _bench("row_filter_scan", run, rounds=rounds)


def bench_hard_filter_polars(*, symbols: int, rounds: int) -> dict[str, float] | None:
    try:
        import polars  # noqa: F401
    except ImportError:
        return None

    from unittest.mock import patch

    from vnpy_ashare.screener.hard_filters import apply_recipe_filters

    rows = [row.to_dict() for row in make_synthetic_quote_rows(symbols)]
    inactive_board = __import__(
        "vnpy_ashare.config.trading_universe",
        fromlist=["MarketBoardFilter"],
    ).MarketBoardFilter(active=False, boards=frozenset())

    patches = [
        patch("vnpy_ashare.screener.hard_filters.recipe_exclude_st_enabled", return_value=False),
        patch("vnpy_ashare.screener.hard_filters.recipe_exclude_suspended_enabled", return_value=False),
        patch("vnpy_ashare.screener.hard_filters.recipe_exclude_new_listing_enabled", return_value=False),
        patch("vnpy_ashare.screener.hard_filters.recipe_exclude_limit_board_enabled", return_value=False),
        patch("vnpy_ashare.screener.hard_filters.recipe_exclude_one_word_enabled", return_value=False),
        patch("vnpy_ashare.screener.hard_filters.recipe_allowed_industries", return_value=frozenset()),
        patch("vnpy_ashare.screener.hard_filters.resolve_market_board_filter", return_value=inactive_board),
        patch("vnpy_ashare.screener.hard_filters.recipe_min_amount_yuan", return_value=30_000_000.0),
        patch("vnpy_ashare.screener.hard_filters.recipe_min_total_mv_wan", return_value=0.0),
    ]

    def run() -> list[dict]:
        for item in patches:
            item.start()
        try:
            import os

            return apply_recipe_filters(rows)
        finally:
            for item in reversed(patches):
                item.stop()

    return _bench("hard_filter_polars", run, rounds=rounds)


def bench_redis_quote_load(*, rounds: int) -> dict[str, float]:
    from vnpy_ashare.screener.data.quotes_loader import load_market_quote_rows

    def run() -> object:
        return load_market_quote_rows()

    return _bench("redis.load_market_quote_rows", run, rounds=rounds)


def bench_radar_leader_pick(*, rounds: int) -> dict[str, float]:
    from vnpy_ashare.quotes.radar.loaders.load import load_radar_cards_batch

    def run() -> object:
        loaded, errors = load_radar_cards_batch([("leader_pick", {})])
        if errors:
            raise RuntimeError("; ".join(f"{key}: {value}" for key, value in errors.items()))
        return loaded

    return _bench("radar.leader_pick", run, rounds=rounds)


def bench_quote_snapshot_compact_roundtrip(*, symbols: int, rounds: int) -> dict[str, float] | None:
    import os

    from vnpy_ashare.quotes.core.quote_redis_codec import encode_quote_hash

    if os.getenv("ZAK_REDIS_QUOTE_COMPACT", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return None

    quotes = make_synthetic_quote_snapshots(symbols)

    def run() -> list[QuoteSnapshot | None]:
        parsed: list[QuoteSnapshot | None] = []
        for quote in quotes.values():
            parsed.append(QuoteSnapshot.from_redis_hash(encode_quote_hash(quote)))
        return parsed

    return _bench("quote_snapshot_compact_roundtrip", run, rounds=rounds)


def bench_recipe(*, recipe_id: str, rounds: int) -> dict[str, float]:
    from vnpy_ashare.screener.recipe.recipe_runner import run_recipe

    def run() -> object:
        return run_recipe(recipe_id)

    return _bench(f"recipe.{recipe_id}", run, rounds=rounds)


def _print_row(row: dict[str, float]) -> None:
    name = row["name"]
    print(
        f"{name:32s}  p50={row['p50_ms']:8.1f}ms  p95={row['p95_ms']:8.1f}ms  "
        f"min={row['min_ms']:8.1f}ms  max={row['max_ms']:8.1f}ms  "
        f"n={int(row['result_size'])}  rounds={int(row['rounds'])}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="zak 热路径性能基准")
    parser.add_argument("--symbols", type=int, default=5000, help="synthetic 标的数量")
    parser.add_argument("--rounds", type=int, default=5, help="每项重复次数")
    parser.add_argument(
        "--integration",
        choices=("redis", "recipe", "radar"),
        help="集成基准（需 Redis / 行情数据）",
    )
    parser.add_argument("--recipe", default="intraday_multi", help="--integration recipe 时使用的 recipe_id")
    parser.add_argument("--json", action="store_true", help="JSON 行输出（便于 CI 解析）")
    parser.add_argument("--trace-summary", action="store_true", help="结束后输出 perf trace Top 5")
    args = parser.parse_args(argv)

    if args.trace_summary:
        import os

        os.environ.setdefault("ZAK_PERF_TRACE", "1")
        from vnpy_common.perf_trace import tracer

        tracer.reset()

    rows: list[dict[str, float]] = []
    if args.integration == "redis":
        rows.append(bench_redis_quote_load(rounds=args.rounds))
    elif args.integration == "recipe":
        rows.append(bench_recipe(recipe_id=args.recipe, rounds=max(1, min(args.rounds, 3))))
    elif args.integration == "radar":
        rows.append(bench_radar_leader_pick(rounds=max(1, min(args.rounds, 3))))
    else:
        rows.extend(
            [
                bench_quote_snapshot_roundtrip(symbols=args.symbols, rounds=args.rounds),
                bench_market_rank_sort(symbols=args.symbols, rounds=args.rounds),
                bench_row_filter_scan(symbols=args.symbols, rounds=args.rounds),
            ]
        )
        polars_row = bench_hard_filter_polars(symbols=args.symbols, rounds=args.rounds)
        if polars_row is not None:
            rows.append(polars_row)
        compact_row = bench_quote_snapshot_compact_roundtrip(symbols=args.symbols, rounds=args.rounds)
        if compact_row is not None:
            rows.append(compact_row)

    if args.json:
        import json

        print(json.dumps({"mode": args.integration or "synthetic", "rows": rows}, ensure_ascii=False))
    else:
        print(f"bench symbols={args.symbols} rounds={args.rounds} mode={args.integration or 'synthetic'}")
        for row in rows:
            _print_row(row)

    if args.trace_summary:
        from vnpy_common.perf_trace import tracer

        print()
        print(tracer.baseline_report([], top_n=5, title="perf trace summary"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
