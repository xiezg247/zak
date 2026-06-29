"""雷达展望扫描与缓存测试。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from vnpy_ashare.quotes.radar.radar_horizon_cache import (
    get_horizon_cache,
    horizon_cache_storage_key,
    put_horizon_cache,
)
from vnpy_ashare.quotes.radar.radar_horizon_scan import (
    HorizonScanStats,
    horizon_empty_message,
    local_daily_k_insufficient,
    prefilter_horizon_universe,
)


def test_horizon_cache_storage_key_includes_strategy() -> None:
    assert horizon_cache_storage_key("watch_next", "AshareDoubleMaStrategy:10:20") == ("watch_next|AshareDoubleMaStrategy:10:20")


def test_horizon_cache_storage_key_without_strategy() -> None:
    assert horizon_cache_storage_key("watch_next", "") == "watch_next"


@pytest.fixture
def horizon_cache_db(tmp_path, monkeypatch):
    db_path = tmp_path / "radar_horizon_cache.db"
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_horizon_cache._db_path",
        lambda: db_path,
    )
    yield


def test_get_horizon_cache_strategy_isolation(horizon_cache_db) -> None:
    key_a = "StrategyA:1:2"
    key_b = "StrategyB:3:4"
    put_horizon_cache(
        "watch_next",
        (),
        scanned_total=10,
        excluded_count=1,
        prefilter_total=5,
        refined_total=3,
        kline_missing=0,
        strategy_key=key_a,
    )
    put_horizon_cache(
        "watch_next",
        (),
        scanned_total=20,
        excluded_count=2,
        prefilter_total=8,
        refined_total=6,
        kline_missing=1,
        strategy_key=key_b,
    )
    entry_a = get_horizon_cache("watch_next", strategy_key=key_a)
    entry_b = get_horizon_cache("watch_next", strategy_key=key_b)
    assert entry_a is not None
    assert entry_b is not None
    assert entry_a.scanned_total == 10
    assert entry_b.scanned_total == 20


def test_local_daily_k_insufficient_requires_empty_refined() -> None:
    stats = HorizonScanStats(
        scanned_total=5000,
        excluded_count=3,
        prefilter_total=100,
        refined_total=0,
        kline_missing=60,
    )
    assert local_daily_k_insufficient(stats)

    stats_with_refined = HorizonScanStats(
        scanned_total=5000,
        excluded_count=3,
        prefilter_total=100,
        refined_total=10,
        kline_missing=90,
    )
    assert not local_daily_k_insufficient(stats_with_refined)


def test_horizon_empty_message_no_local_k() -> None:
    stats = HorizonScanStats(scanned_total=100, excluded_count=0, prefilter_total=0, refined_total=0, kline_missing=0)
    with patch(
        "vnpy_ashare.quotes.radar.radar_horizon_scan.collect_daily_k_ready_vt_symbols",
        return_value=set(),
    ):
        message = horizon_empty_message(stats, card_title="未来·关注")
    assert "本地暂无日 K" in message


def test_prefilter_skips_symbols_without_local_daily_k() -> None:
    quote_rows = [
        {"vt_symbol": "600000.SSE", "amount": 1e9, "turnover_rate": 2.0},
        {"vt_symbol": "000001.SZSE", "amount": 2e9, "turnover_rate": 3.0},
    ]
    snapshot = type("Snap", (), {"rows": quote_rows, "total": len(quote_rows)})()

    with patch(
        "vnpy_ashare.quotes.radar.radar_horizon_scan.load_screening_quote_snapshot",
        return_value=snapshot,
    ):
        with patch(
            "vnpy_ashare.quotes.radar.radar_horizon_scan.apply_recipe_filters",
            side_effect=lambda rows: rows,
        ):
            with patch(
                "vnpy_ashare.quotes.radar.radar_horizon_scan.collect_daily_k_ready_vt_symbols",
                return_value={"600000.SSE"},
            ):
                prefilter, stats = prefilter_horizon_universe(set(), max_items=10)

    assert prefilter == ["600000.SSE"]
    assert stats.prefilter_total == 1
