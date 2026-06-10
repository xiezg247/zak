"""TickFlow 行情拉取。"""

from __future__ import annotations

from vnpy_ashare.domain.models import StockItem
from vnpy_ashare.domain.quote_time import resolve_trade_time_from_tickflow_row
from vnpy_ashare.quotes.snapshot import QuoteSnapshot
from vnpy_tickflow.client import get_tickflow_client

MARKET_INDICES: list[tuple[str, str]] = [
    ("000001.SH", "上证指数"),
    ("399001.SZ", "深证成指"),
    ("399006.SZ", "创业板指"),
    ("000688.SH", "科创50"),
    ("899050.BJ", "北证50"),
]

QUOTE_BATCH_SIZE = 80


def parse_quote_row(row: dict) -> QuoteSnapshot:
    name = str(row.get("ext.name", "") or row.get("name", ""))
    change_pct = float(row.get("ext.change_pct", 0) or 0)
    change_amount = float(row.get("ext.change_amount", 0) or 0)
    turnover_rate = float(row.get("ext.turnover_rate", 0) or 0)
    amplitude = float(row.get("ext.amplitude", 0) or 0)

    return QuoteSnapshot(
        symbol=str(row.get("symbol", "")),
        name=name,
        last_price=float(row.get("last_price", 0) or 0),
        prev_close=float(row.get("prev_close", 0) or 0),
        open_price=float(row.get("open", 0) or 0),
        high_price=float(row.get("high", 0) or 0),
        low_price=float(row.get("low", 0) or 0),
        change_amount=change_amount,
        change_pct=change_pct * 100,
        turnover_rate=turnover_rate * 100,
        volume=float(row.get("volume", 0) or 0),
        amount=float(row.get("amount", 0) or 0),
        amplitude=amplitude * 100,
        trade_time=resolve_trade_time_from_tickflow_row(row),
    )


def fetch_quotes_from_tickflow(items: list[StockItem]) -> dict[str, QuoteSnapshot]:
    if not items:
        return {}

    client = get_tickflow_client()
    tf_symbols = [item.tickflow_symbol for item in items]
    result: dict[str, QuoteSnapshot] = {}

    for start in range(0, len(tf_symbols), QUOTE_BATCH_SIZE):
        batch = tf_symbols[start : start + QUOTE_BATCH_SIZE]
        df = client.quotes.get(symbols=batch, as_dataframe=True)
        if df is None or df.empty:
            continue
        for idx, row in df.iterrows():
            data = row.to_dict()
            if not data.get("symbol"):
                data["symbol"] = str(idx)
            quote = parse_quote_row(data)
            result[quote.symbol] = quote

    return result


def fetch_index_ticker() -> list[tuple[str, QuoteSnapshot]]:
    client = get_tickflow_client()
    symbols = [code for code, _ in MARKET_INDICES]
    df = client.quotes.get(symbols=symbols, as_dataframe=True)
    name_map = dict(MARKET_INDICES)
    rows: list[tuple[str, QuoteSnapshot]] = []

    if df is None or df.empty:
        return rows

    for _, row in df.iterrows():
        quote = parse_quote_row(row.to_dict())
        label = name_map.get(quote.symbol, quote.symbol)
        rows.append((label, quote))
    return rows


__all__ = [
    "MARKET_INDICES",
    "QUOTE_BATCH_SIZE",
    "fetch_index_ticker",
    "fetch_quotes_from_tickflow",
    "get_tickflow_client",
    "parse_quote_row",
]
