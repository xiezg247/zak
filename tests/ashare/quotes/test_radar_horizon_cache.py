"""雷达展望缓存键与读写隔离测试。"""

from __future__ import annotations

import pytest

from vnpy_ashare.quotes.radar.radar_horizon_cache import (
    get_horizon_cache,
    horizon_cache_storage_key,
    put_horizon_cache,
)


def test_horizon_cache_storage_key_includes_strategy() -> None:
    assert horizon_cache_storage_key("watch_next", "AshareDoubleMaStrategy:10:20") == (
        "watch_next|AshareDoubleMaStrategy:10:20"
    )


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


def test_get_horizon_cache_rejects_legacy_row_for_non_empty_strategy_key(
    horizon_cache_db,
) -> None:
    put_horizon_cache(
        "watch_next",
        (),
        scanned_total=100,
        excluded_count=0,
        prefilter_total=50,
        refined_total=10,
        kline_missing=0,
        strategy_key="",
    )
    assert get_horizon_cache("watch_next", strategy_key="AshareDoubleMaStrategy:10:20") is None
    legacy = get_horizon_cache("watch_next", strategy_key="")
    assert legacy is not None
    assert legacy.strategy_key == ""


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


def test_get_horizon_cache_returns_raw_rows_without_quote_enrich(horizon_cache_db) -> None:
    from vnpy_ashare.quotes.radar.radar_models import RadarRow, radar_row_to_cache_dict

    payload_row = radar_row_to_cache_dict(
        RadarRow(
            vt_symbol="601916.SSE",
            name="浙商银行",
            symbol="601916",
            price=3.0,
            change_pct=-1.0,
            metric_label="买入",
            metric_value="80",
            sub_label="事件",
            sub_value="—",
        )
    )
    put_horizon_cache(
        "watch_next",
        (),
        scanned_total=1,
        excluded_count=0,
        prefilter_total=1,
        refined_total=1,
        kline_missing=0,
        strategy_key="test",
    )
    from vnpy_ashare.quotes.radar import radar_horizon_cache as cache_mod

    with cache_mod._connect() as conn:
        import json

        conn.execute(
            "UPDATE radar_horizon_cache SET rows_json = ? WHERE variant = ?",
            (json.dumps([payload_row], ensure_ascii=False), "watch_next|test"),
        )
    entry = get_horizon_cache("watch_next", strategy_key="test")
    assert entry is not None
    assert len(entry.rows) == 1
    assert entry.rows[0].sub_label == "事件"
    assert entry.rows[0].sub_value == "—"
