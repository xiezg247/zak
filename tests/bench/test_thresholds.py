"""bench/thresholds 单元测试。"""

from __future__ import annotations

import os

import pytest

import tests._bootstrap  # noqa: F401
from bench.thresholds import (
    check_live_regression,
    check_synthetic_regression,
    live_p95_limit_ms,
    redis_bench_ready,
    scaled_p95_limit_ms,
)


def test_live_p95_limit_recipe_prefix() -> None:
    assert live_p95_limit_ms("recipe.intraday_multi") == 4500.0
    assert live_p95_limit_ms("recipe.custom") == 4500.0


def test_check_live_regression_violation() -> None:
    rows = [{"name": "radar.leader_pick", "p95_ms": 1300.0}]
    violations = check_live_regression(rows)
    assert len(violations) == 1
    assert "radar.leader_pick" in violations[0]


def test_check_synthetic_passes_small_row() -> None:
    rows = [{"name": "market_rank_sort", "p95_ms": 0.1}]
    assert check_synthetic_regression(rows, symbols=500) == []


@pytest.mark.skipif(not os.getenv("ZAK_BENCH_LIVE"), reason="set ZAK_BENCH_LIVE=1 to run integration live bench")
def test_live_redis_bench_when_env_ready() -> None:
    if not redis_bench_ready():
        pytest.skip("Redis 无全市场行情")
    from bench.run_hotpaths import bench_redis_quote_load

    row = bench_redis_quote_load(rounds=2)
    assert check_live_regression([row]) == []
