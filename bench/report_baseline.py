#!/usr/bin/env python3
"""生成 zak 性能基线报告（Phase 0）。

Synthetic 模式离线可跑；``--live`` 追加 Redis / 选股 / 雷达集成项（需环境）::

    uv run python bench/report_baseline.py
    ZAK_PERF_TRACE=1 uv run python bench/report_baseline.py --live
    uv run python bench/report_baseline.py --output bench/reports/latest.txt
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bench.run_hotpaths import (  # noqa: E402
    bench_radar_leader_pick,
    bench_recipe,
    bench_redis_quote_load,
    run_synthetic_benches,
)
from bench.thresholds import check_live_regression, check_synthetic_regression  # noqa: E402
from vnpy_common.perf_trace import perf_trace_enabled, tracer  # noqa: E402


def _run_synthetic(*, symbols: int, rounds: int) -> list[dict[str, float]]:
    return run_synthetic_benches(symbols=symbols, rounds=rounds)


def _run_live(*, rounds: int, recipe_id: str) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    try:
        rows.append(bench_redis_quote_load(rounds=rounds))
    except Exception as exc:
        print(f"skip redis bench: {exc}", file=sys.stderr)
    try:
        rows.append(bench_recipe(recipe_id=recipe_id, rounds=max(1, min(rounds, 3))))
    except Exception as exc:
        print(f"skip recipe bench: {exc}", file=sys.stderr)
    try:
        rows.append(bench_radar_leader_pick(rounds=max(1, min(rounds, 3))))
    except Exception as exc:
        print(f"skip radar bench: {exc}", file=sys.stderr)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="zak 性能基线报告")
    parser.add_argument("--symbols", type=int, default=5000, help="synthetic 标的数量")
    parser.add_argument("--rounds", type=int, default=5, help="每项重复次数")
    parser.add_argument("--live", action="store_true", help="追加 Redis / recipe / radar 集成项")
    parser.add_argument("--recipe", default="intraday_multi", help="live 模式 recipe_id")
    parser.add_argument("--top", type=int, default=5, help="Top N 热点 span")
    parser.add_argument("--output", type=Path, help="写入报告文件")
    parser.add_argument(
        "--check",
        action="store_true",
        help="synthetic 项 P95 超过 bench/thresholds.py 上限时 exit 1",
    )
    args = parser.parse_args(argv)

    if perf_trace_enabled():
        tracer.reset()

    synthetic_rows = _run_synthetic(symbols=args.symbols, rounds=args.rounds)
    bench_rows = list(synthetic_rows)
    if args.live:
        bench_rows.extend(_run_live(rounds=args.rounds, recipe_id=args.recipe))

    title = f"zak 性能基线报告 ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
    report = tracer.baseline_report(bench_rows, top_n=args.top, title=title)
    print(report)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")
        print(f"\nwritten: {args.output}")

    if perf_trace_enabled():
        tracer.summary("baseline trace")

    if args.check:
        violations = check_synthetic_regression(synthetic_rows, symbols=args.symbols)
        if args.live:
            live_rows = bench_rows[len(synthetic_rows) :]
            violations.extend(check_live_regression(live_rows))
        if violations:
            for line in violations:
                print(f"REGRESSION: {line}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
