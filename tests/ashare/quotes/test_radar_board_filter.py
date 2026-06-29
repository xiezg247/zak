"""雷达页尊重 RECIPE_ALLOWED / ASHARE_TRADING_BOARDS 板块白名单。"""

from __future__ import annotations

import os

import pytest

import tests._bootstrap  # noqa: F401
from vnpy_ashare.config.constants.recipe import ENV_ALLOWED_MARKET_BOARDS
from vnpy_ashare.config.constants.trading import ENV_TRADING_BOARDS
from vnpy_ashare.domain.market.quote_row import coerce_quote_rows
from vnpy_ashare.quotes.radar.radar_leader_pick import build_leader_candidate_pool
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesSnapshot
from vnpy_ashare.screener.data.screening_context import ScreeningContext, screening_context_scope
from vnpy_ashare.screener.data.screening_sentiment_prefilter import apply_recipe_prefilter_to_context
from vnpy_ashare.screener.dimensions.sector_strength import run_sector_strength
from vnpy_ashare.screener.hard_filter_prefs import HardFilterPrefs, save_hard_filter_prefs
from vnpy_ashare.screener.hard_filters import filter_vt_symbols_by_recipe_market_board


@pytest.fixture(autouse=True)
def _reset_hard_filter_prefs() -> None:
    save_hard_filter_prefs(
        HardFilterPrefs(
            exclude_st=False,
            exclude_suspended=False,
            min_amount_wan=0.0,
            min_total_mv_yi=0.0,
            exclude_new_listing=False,
            min_listing_days=60,
            exclude_limit_board=False,
            allowed_industries="",
            allowed_market_boards="",
        )
    )
    yield
    for key in (ENV_TRADING_BOARDS, ENV_ALLOWED_MARKET_BOARDS):
        os.environ.pop(key, None)


def _mixed_snapshot() -> MarketQuotesSnapshot:
    rows = coerce_quote_rows(
        [
            {
                "symbol": "600519",
                "vt_symbol": "600519.SSE",
                "name": "茅台",
                "change_pct": 8.0,
                "amount": 1_000_000,
                "industry": "白酒",
            },
            {
                "symbol": "600036",
                "vt_symbol": "600036.SSE",
                "name": "招行",
                "change_pct": 7.5,
                "amount": 900_000,
                "industry": "白酒",
            },
            {
                "symbol": "601318",
                "vt_symbol": "601318.SSE",
                "name": "平安",
                "change_pct": 6.5,
                "amount": 800_000,
                "industry": "白酒",
            },
            {
                "symbol": "300750",
                "vt_symbol": "300750.SZSE",
                "name": "宁德",
                "change_pct": 8.0,
                "amount": 2_000_000,
                "industry": "电池",
            },
        ]
    )
    return MarketQuotesSnapshot(rows=rows, updated_at="2026-01-01", total=4, source="test")


def test_apply_recipe_prefilter_to_context_keeps_main_board_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_TRADING_BOARDS, "沪深主板")
    monkeypatch.setenv(ENV_ALLOWED_MARKET_BOARDS, "沪深主板")

    ctx = ScreeningContext()
    ctx._snapshot_loaded = True
    ctx._snapshot = _mixed_snapshot()

    apply_recipe_prefilter_to_context(ctx)

    assert ctx._snapshot is not None
    symbols = [str(row.get("symbol")) for row in ctx._snapshot.rows]
    assert symbols == ["600519", "600036", "601318"]
    assert ctx._snapshot.total == 3


def test_run_sector_strength_uses_prefiltered_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_TRADING_BOARDS, "沪深主板")
    monkeypatch.setenv(ENV_ALLOWED_MARKET_BOARDS, "沪深主板")

    def _attach(rows):
        return rows

    monkeypatch.setattr(
        "vnpy_ashare.screener.dimensions.sector_strength.attach_industry",
        _attach,
    )

    with screening_context_scope() as ctx:
        ctx._snapshot_loaded = True
        ctx._snapshot = _mixed_snapshot()
        apply_recipe_prefilter_to_context(ctx)
        hits, _total = run_sector_strength(10, weight=1.0)

    assert hits
    assert all(str(hit.row.get("symbol")) in {"600519", "600036", "601318"} for hit in hits)
    assert all(str(hit.row.get("symbol")) != "300750" for hit in hits)


def test_build_leader_candidate_pool_all_market_respects_board_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_TRADING_BOARDS, "沪深主板")
    monkeypatch.setenv(ENV_ALLOWED_MARKET_BOARDS, "沪深主板")

    with screening_context_scope() as ctx:
        ctx._snapshot_loaded = True
        ctx._snapshot = _mixed_snapshot()
        apply_recipe_prefilter_to_context(ctx)
        pool, _total = build_leader_candidate_pool(variant="all_market", pool_size=20)

    assert pool
    assert all(str(row.get("symbol")) in {"600519", "600036"} for row in pool)
    assert all(str(row.get("symbol")) != "300750" for row in pool)


def test_filter_vt_symbols_by_recipe_market_board() -> None:
    os.environ[ENV_TRADING_BOARDS] = "沪深主板"
    os.environ[ENV_ALLOWED_MARKET_BOARDS] = "沪深主板"

    filtered = filter_vt_symbols_by_recipe_market_board(
        ["600519.SSE", "300750.SZSE", "688981.SSE"],
    )
    assert filtered == ["600519.SSE"]
