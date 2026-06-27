"""热路径 synthetic 基准：smoke + P95 回归门槛。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CI_SYMBOLS = 500
CI_ROUNDS = 3


def test_bench_synthetic_smoke() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "bench" / "run_hotpaths.py"),
            "--symbols",
            str(CI_SYMBOLS),
            "--rounds",
            str(CI_ROUNDS),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "quote_snapshot_roundtrip" in proc.stdout
    assert "row_filter_scan" in proc.stdout


def test_bench_synthetic_p95_regression() -> None:
    from bench.run_hotpaths import run_synthetic_benches
    from bench.thresholds import check_synthetic_regression

    rows = run_synthetic_benches(symbols=CI_SYMBOLS, rounds=CI_ROUNDS)
    violations = check_synthetic_regression(rows, symbols=CI_SYMBOLS)
    assert not violations, "\n".join(violations)


def test_bench_cli_check_flag() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "bench" / "run_hotpaths.py"),
            "--symbols",
            str(CI_SYMBOLS),
            "--rounds",
            str(CI_ROUNDS),
            "--check",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_scaled_p95_limits() -> None:
    from bench.thresholds import scaled_p95_limit_ms

    assert scaled_p95_limit_ms("quote_snapshot_roundtrip", 5000) == 200.0
    assert scaled_p95_limit_ms("quote_snapshot_roundtrip", 500) == 20.0
    assert scaled_p95_limit_ms("unknown", 500) is None
