"""QuoteRow 领域模型测试。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.market.quote_row import (
    QuoteRow,
    coerce_quote_row,
    quote_row_from_mapping,
    quote_row_from_stock_and_snapshot,
)
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.quotes.core.quote_rows import get_market_quotes_cache, set_market_quote_rows_cache
from vnpy_ashare.quotes.core.snapshot import QuoteSnapshot
from vnpy_ashare.trading.signals.intraday_seal_time import attach_first_time_fields, infer_prev_close_from_row


def test_quote_row_dict_compat() -> None:
    row = QuoteRow(symbol="600000", vt_symbol="600000.SSE", last_price=11.0, change_pct=10.0, close=11.0)
    as_dict = dict(row)
    assert as_dict["symbol"] == "600000"
    assert as_dict["last_price"] == 11.0
    assert row.get("close") == 11.0


def test_quote_row_from_stock_and_snapshot() -> None:
    item = StockItem(symbol="600000", exchange=Exchange.SSE, name="浦发银行")
    quote = QuoteSnapshot(
        symbol="600000",
        name="浦发银行",
        last_price=10.5,
        prev_close=10.0,
        open_price=10.1,
        high_price=10.6,
        low_price=10.0,
        change_amount=0.5,
        change_pct=5.0,
        turnover_rate=1.2,
        volume=1000,
        amount=10500,
    )
    row = quote_row_from_stock_and_snapshot(item, quote)
    assert row.vt_symbol == "600000.SSE"
    assert row.last_price == 10.5
    assert row.get("close") == 10.5


def test_quote_row_extra_fields_and_mutation() -> None:
    row = QuoteRow(symbol="000001", vt_symbol="000001.SZSE")
    row["pattern_score"] = 88.5
    assert row.get("pattern_score") == 88.5
    assert row.to_dict()["pattern_score"] == 88.5


def test_coerce_quote_row_from_dict() -> None:
    raw = {"symbol": "000001", "vt_symbol": "000001.SZSE", "last_price": 12.0, "change_pct": 2.0}
    row = coerce_quote_row(raw)
    assert isinstance(row, QuoteRow)
    assert infer_prev_close_from_row(row) == round(12.0 / 1.02, 4)


def test_market_quote_rows_cache_roundtrip() -> None:
    set_market_quote_rows_cache(
        [
            QuoteRow(symbol="600000", vt_symbol="600000.SSE", last_price=10.0),
            {"symbol": "000001", "vt_symbol": "000001.SZSE", "last_price": 11.0},
        ]
    )
    cached = get_market_quotes_cache()
    assert len(cached) == 2
    assert all(isinstance(row, QuoteRow) for row in cached)
    set_market_quote_rows_cache([])


def test_attach_first_time_fields_on_quote_row() -> None:
    row = quote_row_from_mapping({"vt_symbol": "600000.SSE", "symbol": "600000", "last_price": 11.0, "change_pct": 10.0})
    rows = [row]
    attach_first_time_fields(rows, max_intraday_fetch=0)
    assert rows[0].get("first_time") in (None, "")
