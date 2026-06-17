"""连板梯队汇总测试。"""

from __future__ import annotations

from vnpy_ashare.quotes.market.limit_ladder_summary import compute_limit_ladder_counts
from vnpy_ashare.quotes.radar.radar_limit_ladder import count_ladder_buckets


def test_compute_limit_ladder_counts_empty() -> None:
    counts = compute_limit_ladder_counts([])
    assert counts["首板"] == 0
    assert counts["5板+"] == 0


def test_count_ladder_buckets() -> None:
    rows = [{"limit_times": 1}, {"limit_times": 3}]
    counts = count_ladder_buckets(rows)
    assert counts["首板"] == 1
    assert counts["3板"] == 1
