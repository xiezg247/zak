"""风险指标单元测试。"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from vnpy_ashare.services.analysis_detail.risk_metrics import compute_beta_vs_hs300


def _bars(closes: list[float]):
    base = date(2025, 1, 1)
    return [SimpleNamespace(datetime=base + timedelta(days=index), close_price=price) for index, price in enumerate(closes)]


def test_compute_beta_vs_hs300_parallel_moves():
    stock = _bars([10, 10.5, 11, 11.5, 12, 12.5, 13, 13.5, 14, 14.5, 15])
    bench = _bars([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110])
    beta = compute_beta_vs_hs300(stock, bench, lookback=10)
    assert beta is not None
    assert beta > 0.5
