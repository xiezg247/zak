"""ScreeningContext 与量比映射缓存测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.screener.data.quotes_loader import MarketQuotesSnapshot
from vnpy_ashare.screener.data.screening_context import (
    fetch_volume_ratio_map_uncached,
    get_volume_ratio_map,
    preload_screening_context,
    screening_context_scope,
)
from vnpy_ashare.screener.dimensions.volume_ratio import run_volume_ratio


def test_screening_context_caches_quote_snapshot() -> None:
    snapshot = MarketQuotesSnapshot(rows=[{"vt_symbol": "600000.SSE"}], updated_at="x", total=1)
    calls = 0

    def _load():
        nonlocal calls
        calls += 1
        return snapshot

    with patch(
        "vnpy_ashare.screener.data.screening_context.load_screening_quote_snapshot_uncached",
        side_effect=_load,
    ):
        with screening_context_scope() as ctx:
            preload_screening_context(ctx)
            from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot

            first = load_screening_quote_snapshot()
            second = load_screening_quote_snapshot()

    assert calls == 1
    assert first.total == second.total == 1


def test_volume_ratio_skips_rows_without_ratio() -> None:
    snapshot = MarketQuotesSnapshot(
        rows=[
            {"vt_symbol": "600000.SSE", "symbol": "600000", "volume": 999_999, "change_pct": 1.0},
            {"vt_symbol": "000001.SZSE", "symbol": "000001", "volume": 1, "amount": 50_000_000, "change_pct": 2.0},
        ],
        updated_at="x",
        total=2,
    )

    with (
        patch(
            "vnpy_ashare.screener.dimensions.volume_ratio.load_screening_quote_snapshot",
            return_value=snapshot,
        ),
        patch(
            "vnpy_ashare.screener.dimensions.volume_ratio.get_volume_ratio_map",
            return_value={"000001.SZSE": 3.5},
        ),
    ):
        hits, scanned = run_volume_ratio(5, weight=0.2)

    assert scanned == 2
    assert len(hits) == 1
    assert hits[0].vt_symbol == "000001.SZSE"
    assert hits[0].row["volume_ratio"] == 3.5


def test_get_volume_ratio_map_uses_context_cache() -> None:
    calls = 0

    def _fetch():
        nonlocal calls
        calls += 1
        return {"600000.SSE": 2.0}

    with patch(
        "vnpy_ashare.screener.data.screening_context.fetch_volume_ratio_map_uncached",
        side_effect=_fetch,
    ):
        with screening_context_scope() as ctx:
            preload_screening_context(ctx)
            first = get_volume_ratio_map()
            second = get_volume_ratio_map()

    assert calls == 1
    assert first == second == {"600000.SSE": 2.0}


def test_fetch_volume_ratio_map_uncached_empty_on_error() -> None:
    with patch(
        "vnpy_ashare.screener.data.screening_context.fetch_daily_basic",
        side_effect=RuntimeError("boom"),
    ):
        assert fetch_volume_ratio_map_uncached() == {}
