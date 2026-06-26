"""热路径 synthetic 基准 smoke 测试（CI 可跑，不断言绝对耗时）。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_bench_synthetic_smoke() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "bench" / "run_hotpaths.py"), "--symbols", "500", "--rounds", "2"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "quote_snapshot_roundtrip" in proc.stdout
    assert "row_filter_scan" in proc.stdout
