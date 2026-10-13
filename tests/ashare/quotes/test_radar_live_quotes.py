"""盘中实时行情合并行为测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vnpy_ashare.domain.market.quote_row import QuoteRow
from vnpy_ashare.quotes.radar.loaders import RadarRow
from vnpy_ashare.quotes.radar.radar_quotes import merge_row_quotes, quotes_for_vt_symbols
from vnpy_ashare.quotes.radar.radar_enrich import enrich_radar_rows


def test_merge_row_quotes_prefers_live_cache_during_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_quotes.is_ashare_trading_session", lambda: True)
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_enrich.is_ashare_trading_session", lambda: True)
    stale = QuoteRow(
        symbol="600000",
        name="浦发",
        vt_symbol="600000.SSE",
        exchange="SSE",
        last_price=10.0,
        change_pct=1.0,
    )
    live = QuoteRow(
        symbol="600000",
        name="浦发",
        vt_symbol="600000.SSE",
        exchange="SSE",
        last_price=10.8,
        change_pct=2.5,
    )
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_quotes.quote_map", lambda: {"600000.SSE": live})

    merged = merge_row_quotes(stale)
    assert merged["last_price"] == 10.8
    assert merged["change_pct"] == 2.5


def test_quotes_for_vt_symbols_avoids_full_market_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    """请求 K 只时不得全表 values()/rows ingest。"""
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_quotes.is_ashare_trading_session", lambda: False)

    class _CountingMap(dict):
        values_calls = 0

        def values(self):  # type: ignore[override]
            type(self).values_calls += 1
            return super().values()

    cache = _CountingMap(
        {
            "600000.SSE": QuoteRow(
                symbol="600000",
                name="浦发",
                vt_symbol="600000.SSE",
                exchange="SSE",
                last_price=10.0,
                change_pct=1.0,
            ),
            "600001.SSE": QuoteRow(
                symbol="600001",
                name="其他",
                vt_symbol="600001.SSE",
                exchange="SSE",
                last_price=9.0,
                change_pct=0.5,
            ),
        }
    )
    _CountingMap.values_calls = 0
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_quotes.quote_map", lambda: cache)

    snapshot_rows_iterated = {"n": 0}

    class _Snap:
        @property
        def rows(self):
            snapshot_rows_iterated["n"] += 1
            # 若走到快照，也应只 ingest 请求标的；此处记录被访问
            return [
                {"vt_symbol": "600000.SSE", "last_price": 8.0, "change_pct": 0.1},
                {"vt_symbol": "600099.SSE", "last_price": 7.0, "change_pct": 0.2},
            ]

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_quotes.load_screening_quote_snapshot",
        lambda: _Snap(),
    )
    store = MagicMock()
    store.get_quotes.return_value = {}
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_quotes.get_redis_quote_store", lambda: store)

    quotes = quotes_for_vt_symbols(["600000.SSE"])
    assert quotes["600000.SSE"]["last_price"] == 10.0
    assert _CountingMap.values_calls == 0
    # quote_map 已命中，不应再扫 snapshot.rows
    assert snapshot_rows_iterated["n"] == 0


def test_quotes_for_candidates_delegates_to_vt_symbols(monkeypatch: pytest.MonkeyPatch) -> None:
    from vnpy_ashare.quotes.radar.radar_watchlist_quotes import quotes_for_candidates

    called: list[list[str]] = []

    def _fake(symbols: list[str]) -> dict:
        called.append(list(symbols))
        return {symbols[0]: {"vt_symbol": symbols[0], "last_price": 1.0}}

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_watchlist_quotes.quotes_for_vt_symbols",
        _fake,
    )
    out = quotes_for_candidates(["600000.SSE"])
    assert called == [["600000.SSE"]]
    assert out["600000.SSE"]["last_price"] == 1.0


def test_quotes_for_vt_symbols_prefers_redis_during_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_quotes.is_ashare_trading_session", lambda: True)
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_enrich.is_ashare_trading_session", lambda: True)
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_quotes.quote_map", lambda: {})
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_quotes.load_screening_quote_snapshot",
        lambda: MagicMock(rows=[{"vt_symbol": "600000.SSE", "last_price": 9.0, "change_pct": 0.5}]),
    )

    live_quote = MagicMock()
    live_quote.name = "浦发"
    live_quote.last_price = 11.2
    live_quote.change_pct = 3.3
    live_quote.turnover_rate = 1.2
    live_quote.volume = 1000.0
    live_quote.amount = 2000.0

    store = MagicMock()
    store.get_quotes.return_value = {"600000": live_quote}
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_quotes.get_redis_quote_store", lambda: store)
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_quotes.parse_tickflow_symbol",
        lambda tf, _name: MagicMock(vt_symbol="600000.SSE", symbol="600000"),
    )

    quotes = quotes_for_vt_symbols(["600000.SSE"])
    assert quotes["600000.SSE"]["last_price"] == 11.2
    assert quotes["600000.SSE"]["change_pct"] == 3.3


def test_enrich_radar_rows_updates_price_from_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_quotes.is_ashare_trading_session", lambda: True)
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_enrich.is_ashare_trading_session", lambda: True)
    row = RadarRow(
        vt_symbol="600000.SSE",
        name="浦发",
        symbol="600000",
        price=10.0,
        change_pct=1.0,
        metric_label="涨幅",
        metric_value="+1.00%",
        sub_label="",
        sub_value="",
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_enrich.quotes_for_vt_symbols",
        lambda _symbols: {
            "600000.SSE": {
                "vt_symbol": "600000.SSE",
                "symbol": "600000",
                "last_price": 10.6,
                "change_pct": 2.1,
            }
        },
    )
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_quotes.quote_map", lambda: {})
    from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_enrich.load_screening_quote_snapshot",
        lambda: (_ for _ in ()).throw(MarketQuotesLoadError("skip")),
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_enrich.build_relative_strength_context",
        lambda _rows: None,
    )

    enriched = enrich_radar_rows((row,))
    assert enriched[0].price == 10.6
    assert enriched[0].change_pct == 2.1
