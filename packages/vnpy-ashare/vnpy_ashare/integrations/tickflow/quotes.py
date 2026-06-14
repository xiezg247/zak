"""TickFlow 行情拉取。"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from vnpy_ashare.domain.quote_time import resolve_trade_time_from_tickflow_row
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.quotes.snapshot import QuoteSnapshot
from vnpy_tickflow.client import get_tickflow_client

from vnpy_ashare.domain.market_indices import MARKET_INDICES

QUOTE_BATCH_SIZE = 80
DEFAULT_QUOTE_FETCH_MAX_WORKERS = 4


def quote_fetch_max_workers(*, batch_count: int) -> int:
    """TickFlow 行情 batch 并发数（QUOTE_FETCH_MAX_WORKERS，默认 4）。"""
    raw = os.getenv("QUOTE_FETCH_MAX_WORKERS", str(DEFAULT_QUOTE_FETCH_MAX_WORKERS)).strip()
    try:
        configured = int(raw)
    except ValueError:
        configured = DEFAULT_QUOTE_FETCH_MAX_WORKERS
    configured = max(1, min(configured, 8))
    return min(configured, batch_count)


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


def _quotes_from_dataframe(df) -> dict[str, QuoteSnapshot]:
    if df is None or df.empty:
        return {}
    result: dict[str, QuoteSnapshot] = {}
    for idx, row in df.iterrows():
        data = row.to_dict()
        if not data.get("symbol"):
            data["symbol"] = str(idx)
        quote = parse_quote_row(data)
        result[quote.symbol] = quote
    return result


def _fetch_quote_batch(tf_symbols: list[str]) -> dict[str, QuoteSnapshot]:
    """单 batch 拉取（每线程独立 client）。"""
    if not tf_symbols:
        return {}
    client = get_tickflow_client()
    df = client.quotes.get(symbols=tf_symbols, as_dataframe=True)
    return _quotes_from_dataframe(df)


def fetch_quotes_from_tickflow(
    items: list[StockItem],
    *,
    max_workers: int | None = None,
) -> dict[str, QuoteSnapshot]:
    if not items:
        return {}

    tf_symbols = [item.tickflow_symbol for item in items]
    batches = [tf_symbols[start : start + QUOTE_BATCH_SIZE] for start in range(0, len(tf_symbols), QUOTE_BATCH_SIZE)]
    workers = max_workers if max_workers is not None else quote_fetch_max_workers(batch_count=len(batches))

    if workers <= 1 or len(batches) <= 1:
        client = get_tickflow_client()
        result: dict[str, QuoteSnapshot] = {}
        for batch in batches:
            df = client.quotes.get(symbols=batch, as_dataframe=True)
            result.update(_quotes_from_dataframe(df))
        return result

    result: dict[str, QuoteSnapshot] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for part in pool.map(_fetch_quote_batch, batches):
            result.update(part)
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
