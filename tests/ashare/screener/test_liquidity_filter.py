"""流动性硬过滤测试。"""

from __future__ import annotations

from vnpy_ashare.screener.hard_filters import passes_liquidity_filter


def test_zero_amount_falls_back_to_market_cap() -> None:
    row = {
        "amount": 0.0,
        "circ_mv": 2_000_000.0,
    }
    assert passes_liquidity_filter(row)


def test_positive_amount_still_enforced() -> None:
    row = {
        "amount": 1_000_000.0,
        "circ_mv": 2_000_000.0,
    }
    assert not passes_liquidity_filter(row)

    row_ok = {
        "amount": 50_000_000.0,
        "circ_mv": 2_000_000.0,
    }
    assert passes_liquidity_filter(row_ok)
