"""盘中实时行情合并行为测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vnpy_ashare.domain.market.quote_row import QuoteRow
from vnpy_ashare.quotes.radar.radar_models import enrich_radar_rows, merge_row_quotes, quotes_for_vt_symbols
from vnpy_ashare.quotes.radar.radar_loaders import RadarRow


def test_merge_row_quotes_prefers_live_cache_during_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_models.is_ashare_trading_session", lambda: True)
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
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_models.quote_map", lambda: {"600000.SSE": live})

    merged = merge_row_quotes(stale)
    assert merged["last_price"] == 10.8
    assert merged["change_pct"] == 2.5


def test_quotes_for_vt_symbols_prefers_redis_during_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_models.is_ashare_trading_session", lambda: True)
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_models.quote_map", lambda: {})
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_models.load_screening_quote_snapshot",
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
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_models.get_redis_quote_store", lambda: store)
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_models.parse_tickflow_symbol",
        lambda tf, _name: MagicMock(vt_symbol="600000.SSE", symbol="600000"),
    )

    quotes = quotes_for_vt_symbols(["600000.SSE"])
    assert quotes["600000.SSE"]["last_price"] == 11.2
    assert quotes["600000.SSE"]["change_pct"] == 3.3


def test_enrich_radar_rows_updates_price_from_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_models.is_ashare_trading_session", lambda: True)
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
        "vnpy_ashare.quotes.radar.radar_models.quotes_for_vt_symbols",
        lambda _symbols: {
            "600000.SSE": {
                "vt_symbol": "600000.SSE",
                "symbol": "600000",
                "last_price": 10.6,
                "change_pct": 2.1,
            }
        },
    )
    from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_models.load_screening_quote_snapshot",
        lambda: (_ for _ in ()).throw(MarketQuotesLoadError("skip")),
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_models.build_relative_strength_context",
        lambda _rows: None,
    )

    enriched = enrich_radar_rows((row,))
    assert enriched[0].price == 10.6
    assert enriched[0].change_pct == 2.1
