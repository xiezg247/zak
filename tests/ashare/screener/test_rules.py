"""选股规则单元测试。"""

from __future__ import annotations

from vnpy_ashare.screener.preset.rules import (
    apply_large_cap,
    apply_low_pe,
    apply_moneyflow_in,
    apply_quote_preset,
)


def _quote(symbol: str, **kwargs) -> dict:
    base = {
        "symbol": symbol,
        "name": symbol,
        "vt_symbol": f"{symbol}.SSE",
        "last_price": 10.0,
        "change_pct": 0.0,
        "turnover_rate": 1.0,
        "volume": 1000,
    }
    base.update(kwargs)
    return base


def test_apply_quote_change_top():
    rows = apply_quote_preset(
        "涨幅榜",
        [_quote("A", change_pct=1), _quote("B", change_pct=5)],
        top_n=1,
    )
    assert len(rows) == 1
    assert rows[0]["symbol"] == "B"


def test_apply_quote_custom_range():
    rows = apply_quote_preset(
        "自定义筛选",
        [_quote("A", change_pct=1), _quote("B", change_pct=4), _quote("C", change_pct=8)],
        top_n=10,
        min_change_pct=2.0,
        max_change_pct=5.0,
    )
    assert [row["symbol"] for row in rows] == ["B"]


def test_apply_low_pe():
    rows = apply_low_pe(
        [
            {"symbol": "A", "name": "A", "vt_symbol": "A.SSE", "pe_ttm": 10, "pb": 1.2, "total_mv": 1},
            {"symbol": "B", "name": "B", "vt_symbol": "B.SSE", "pe_ttm": 25, "pb": 2.0, "total_mv": 1},
        ],
        top_n=5,
    )
    assert len(rows) == 1
    assert rows[0]["symbol"] == "A"


def test_apply_large_cap():
    rows = apply_large_cap(
        [
            {"symbol": "A", "name": "A", "vt_symbol": "A.SSE", "total_mv": 600_000},
            {"symbol": "B", "name": "B", "vt_symbol": "B.SSE", "total_mv": 100_000},
        ],
        top_n=5,
    )
    assert len(rows) == 1
    assert rows[0]["symbol"] == "A"


def test_apply_moneyflow_in():
    rows = apply_moneyflow_in(
        [
            {"symbol": "A", "name": "A", "vt_symbol": "A.SSE", "net_mf_amount": 100},
            {"symbol": "B", "name": "B", "vt_symbol": "B.SSE", "net_mf_amount": -10},
            {"symbol": "C", "name": "C", "vt_symbol": "C.SSE", "net_mf_amount": 500},
        ],
        top_n=2,
    )
    assert [row["symbol"] for row in rows] == ["C", "A"]
