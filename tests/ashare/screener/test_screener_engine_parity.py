"""Polars 选股引擎回归测试。"""

from __future__ import annotations

import pytest

from vnpy_ashare.screener.hard_filters import apply_recipe_filters
from vnpy_ashare.screener.preset.rules import apply_quote_preset

polars = pytest.importorskip("polars")


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


def _symbols(rows: list) -> list[str]:
    return [str(r.get("symbol") if isinstance(r, dict) else getattr(r, "symbol", "")) for r in rows]


@pytest.fixture
def disable_pg_side_effects(monkeypatch):
    """硬过滤不触发 PG / Tushare 快照。"""
    monkeypatch.setattr(
        "vnpy_ashare.screener.hard_filters.recipe_exclude_st_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "vnpy_ashare.screener.hard_filters.recipe_exclude_suspended_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "vnpy_ashare.screener.hard_filters.recipe_exclude_new_listing_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "vnpy_ashare.screener.hard_filters.recipe_exclude_limit_board_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "vnpy_ashare.screener.hard_filters.recipe_exclude_one_word_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "vnpy_ashare.screener.hard_filters.recipe_allowed_industries",
        lambda: frozenset(),
    )
    monkeypatch.setattr(
        "vnpy_ashare.screener.hard_filters.resolve_market_board_filter",
        lambda: __import__(
            "vnpy_ashare.config.trading_universe",
            fromlist=["MarketBoardFilter"],
        ).MarketBoardFilter(active=False, boards=frozenset()),
    )
    monkeypatch.setattr(
        "vnpy_ashare.screener.hard_filters.recipe_min_amount_yuan",
        lambda: 30_000_000.0,
    )
    monkeypatch.setattr(
        "vnpy_ashare.screener.hard_filters.recipe_min_total_mv_wan",
        lambda: 0.0,
    )


def test_hard_filter_excludes_low_amount(disable_pg_side_effects, monkeypatch):
    rows = [
        _quote("600001", amount=50_000_000, change_pct=3.0),
        _quote("600002", amount=1_000_000, change_pct=2.0),
        _quote("600003", name="ST测试", amount=50_000_000, change_pct=1.0),
    ]
    monkeypatch.setattr(
        "vnpy_ashare.screener.hard_filters.recipe_exclude_st_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "vnpy_ashare.screener.hard_filters._screening_vt_name_map",
        lambda: {},
    )
    assert _symbols(apply_recipe_filters(rows)) == ["600001"]


def test_hard_filter_one_word(disable_pg_side_effects, monkeypatch):
    rows = [
        _quote(
            "600100",
            change_pct=10.0,
            prev_close=10.0,
            high_price=11.0,
            low_price=10.99,
            amount=100_000_000,
        ),
        _quote(
            "600101",
            change_pct=10.0,
            prev_close=10.0,
            high_price=11.0,
            low_price=10.5,
            amount=100_000_000,
        ),
    ]
    monkeypatch.setattr(
        "vnpy_ashare.screener.hard_filters.recipe_exclude_one_word_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "vnpy_ashare.screener.hard_filters.recipe_min_amount_yuan",
        lambda: 0.0,
    )
    assert _symbols(apply_recipe_filters(rows)) == ["600101"]


def test_hard_filter_limit_board(disable_pg_side_effects, monkeypatch):
    rows = [
        _quote("600200", change_pct=10.0, amount=50_000_000),
        _quote("600201", change_pct=5.0, amount=50_000_000),
    ]
    monkeypatch.setattr(
        "vnpy_ashare.screener.hard_filters.recipe_exclude_limit_board_enabled",
        lambda: True,
    )
    assert _symbols(apply_recipe_filters(rows)) == ["600201"]


def test_quote_preset_change_top(disable_pg_side_effects):
    quotes = [
        _quote("600010", change_pct=1.0),
        _quote("600011", change_pct=5.0),
        _quote("600012", change_pct=3.0),
    ]
    assert _symbols(apply_quote_preset("涨幅榜", quotes, top_n=2)) == ["600011", "600012"]


def test_quote_preset_custom(disable_pg_side_effects):
    quotes = [
        _quote("600020", change_pct=1.0, turnover_rate=1.0),
        _quote("600021", change_pct=4.0, turnover_rate=2.0),
        _quote("600022", change_pct=8.0, turnover_rate=3.0),
    ]
    assert _symbols(
        apply_quote_preset(
            "自定义筛选",
            quotes,
            top_n=5,
            min_change_pct=2.0,
            max_change_pct=5.0,
        )
    ) == ["600021"]


def test_quote_preset_volume_ratio(disable_pg_side_effects, monkeypatch):
    quotes = [
        _quote("600030", volume_ratio=1.2),
        _quote("600031", volume_ratio=3.5),
        _quote("600032", volume_ratio=0.0),
    ]
    monkeypatch.setattr(
        "vnpy_ashare.screener.engine.presets.get_volume_ratio_map",
        lambda: {"600030.SSE": 2.0, "600031.SSE": 4.0},
    )
    monkeypatch.setattr(
        "vnpy_ashare.screener.preset.rules.get_volume_ratio_map",
        lambda: {"600030.SSE": 2.0, "600031.SSE": 4.0},
    )
    assert _symbols(apply_quote_preset("量比排行", quotes, top_n=2)) == ["600031", "600030"]


def test_recipe_sort():
    from vnpy_ashare.screener.engine.recipe_sort import sort_recipe_payloads_polars

    rows = [
        {"symbol": "A", "composite_score": 80.0, "hit_reasons": ["a"]},
        {"symbol": "B", "composite_score": 90.0, "hit_reasons": ["a", "b"]},
        {"symbol": "C", "composite_score": 90.0, "hit_reasons": ["a"]},
    ]
    ordered = [str(row["symbol"]) for row in sort_recipe_payloads_polars([dict(row) for row in rows])]
    assert ordered == ["B", "C", "A"]
