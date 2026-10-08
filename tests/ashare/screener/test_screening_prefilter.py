"""选股快照预过滤纯函数。"""

from __future__ import annotations

from vnpy_ashare.screener.data.screening_prefilter import (
    apply_coarse_quote_filters,
    at_any_limit_board,
    is_beijing_board,
)


def test_at_any_limit_board() -> None:
    assert at_any_limit_board("600000", 9.9)
    assert not at_any_limit_board("600000", 5.0)
    assert at_any_limit_board("300001", 19.6)
    assert not at_any_limit_board("300001", 10.0)


def test_is_beijing_board() -> None:
    assert is_beijing_board("830001")
    assert is_beijing_board("430001")
    assert not is_beijing_board("600000")
    assert not is_beijing_board("")


def test_apply_coarse_quote_filters(monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.screener.hard_filters.recipe_min_amount_yuan",
        lambda: 1_000_000.0,
    )
    monkeypatch.setattr(
        "vnpy_ashare.screener.data.screening_prefilter.get_board_prefilter_boards",
        lambda: frozenset(),
    )
    rows = [
        {"symbol": "600000", "last_price": 10.0, "change_pct": 1.0, "amount": 2_000_000},
        {"symbol": "600001", "last_price": 0.0, "change_pct": 1.0, "amount": 2_000_000},
        {"symbol": "600002", "last_price": 10.0, "change_pct": 10.0, "amount": 2_000_000},
        {"symbol": "600003", "last_price": 10.0, "change_pct": 1.0, "amount": 100},
        {"symbol": "830001", "last_price": 10.0, "change_pct": 1.0, "amount": 2_000_000},
    ]
    kept = apply_coarse_quote_filters(rows)
    assert [r["symbol"] for r in kept] == ["600000"]
