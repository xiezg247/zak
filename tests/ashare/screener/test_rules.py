"""选股规则单元测试。"""

from __future__ import annotations

from vnpy_ashare.screener.preset.rules import (
    apply_large_cap,
    apply_limit_up,
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
        "amount": 50_000_000,
    }
    base.update(kwargs)
    return base


def test_apply_quote_preserves_fundamental_fields(monkeypatch):
    monkeypatch.setattr(
        "vnpy_ashare.screener.preset.rules.apply_screening_filters",
        lambda rows: rows,
    )
    rows = apply_quote_preset(
        "换手率排行",
        [
            _quote(
                "600498",
                source="tushare",
                close=28.5,
                pe_ttm=22.3,
                pb=1.8,
                total_mv=3_500_000,
                circ_mv=3_200_000,
                trade_date="20260613",
                turnover_rate=12.7,
            )
        ],
        top_n=5,
    )
    assert rows[0]["close"] == 28.5
    assert rows[0]["pe_ttm"] == 22.3
    assert rows[0]["pb"] == 1.8
    assert rows[0]["total_mv"] == 3_500_000
    assert rows[0]["trade_date"] == "20260613"


def test_apply_quote_maps_close_from_last_price(monkeypatch):
    monkeypatch.setattr(
        "vnpy_ashare.screener.preset.rules.apply_screening_filters",
        lambda rows: rows,
    )
    rows = apply_quote_preset(
        "涨幅榜",
        [_quote("A", last_price=15.6, change_pct=3.0)],
        top_n=1,
    )
    assert rows[0]["close"] == 15.6


def test_apply_quote_change_top():
    rows = apply_quote_preset(
        "涨幅榜",
        [_quote("A", change_pct=1), _quote("B", change_pct=5)],
        top_n=1,
    )
    assert len(rows) == 1
    assert rows[0]["symbol"] == "B"


def test_apply_quote_excludes_st_and_low_amount():
    rows = apply_quote_preset(
        "涨幅榜",
        [
            _quote("ST", name="ST测试", change_pct=9, amount=100_000_000),
            _quote("LOW", name="小盘", change_pct=8, amount=1_000_000),
            _quote("OK", name="活跃", change_pct=5, amount=40_000_000),
        ],
        top_n=5,
    )
    assert [row["symbol"] for row in rows] == ["OK"]


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
            {"symbol": "A", "name": "A", "vt_symbol": "A.SSE", "pe_ttm": 10, "pb": 1.2, "total_mv": 600_000},
            {"symbol": "B", "name": "B", "vt_symbol": "B.SSE", "pe_ttm": 25, "pb": 2.0, "total_mv": 600_000},
            {"symbol": "C", "name": "C", "vt_symbol": "C.SSE", "pe_ttm": 8, "pb": 1.0, "total_mv": 100_000},
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


def test_apply_moneyflow_in_sets_flow_kind(monkeypatch):
    monkeypatch.setattr(
        "vnpy_ashare.screener.preset.rules.apply_screening_filters",
        lambda rows: rows,
    )
    rows = apply_moneyflow_in(
        [
            {
                "symbol": "600498",
                "name": "烽火通信",
                "vt_symbol": "600498.SSE",
                "net_mf_amount": 62362,
                "buy_elg_amount": 50000,
                "sell_elg_amount": 10000,
                "moneyflow_source": "tushare",
            }
        ],
        top_n=5,
    )
    assert rows[0]["flow_kind"] == "main"


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


def test_apply_quote_strong_up_filters_min_change():
    rows = apply_quote_preset(
        "强势上涨",
        [_quote("A", change_pct=3), _quote("B", change_pct=6), _quote("C", change_pct=8)],
        top_n=5,
    )
    assert [row["symbol"] for row in rows] == ["C", "B"]


def test_apply_quote_volume_ratio(monkeypatch):
    monkeypatch.setattr(
        "vnpy_ashare.screener.preset.rules._sort_by_volume_ratio",
        lambda quotes: sorted(quotes, key=lambda q: q.get("volume_ratio", 0), reverse=True),
    )
    rows = apply_quote_preset(
        "量比排行",
        [
            _quote("A", volume_ratio=1.2),
            _quote("B", volume_ratio=3.5),
            _quote("C", volume_ratio=2.0),
        ],
        top_n=2,
    )
    assert [row["symbol"] for row in rows] == ["B", "C"]


def test_apply_limit_up_sorts_by_limit_times():
    rows = apply_limit_up(
        [
            {"vt_symbol": "000001.SZSE", "name": "A", "limit_times": 1},
            {"vt_symbol": "600000.SSE", "name": "B", "limit_times": 3},
        ],
        top_n=5,
    )
    assert rows[0]["symbol"] == "600000"
    assert rows[0]["limit_times"] == 3
