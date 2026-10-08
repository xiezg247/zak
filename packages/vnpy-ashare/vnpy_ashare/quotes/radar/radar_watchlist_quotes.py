"""自选雷达：候选标的行情补全。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRowLike
from vnpy_ashare.domain.symbols.stock import parse_stock_symbol, parse_tickflow_symbol
from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore
from vnpy_ashare.quotes.radar.radar_quotes import merge_row_quotes, quote_map
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError

__all__ = [
    "has_quote_data",
    "quotes_for_candidates",
]


def _ingest_quote_row(
    row: QuoteRowLike,
    *,
    by_vt: dict[str, dict[str, Any]],
    by_symbol: dict[str, dict[str, Any]],
) -> None:
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    symbol = str(row.get("symbol") or "").strip()
    if not vt_symbol and symbol:
        item = parse_stock_symbol(symbol)
        if item is not None:
            vt_symbol = item.vt_symbol
            row = dict(row)
            row["vt_symbol"] = vt_symbol
    if vt_symbol:
        by_vt[vt_symbol] = dict(row)
    if symbol:
        by_symbol[symbol] = dict(row)


def quotes_for_candidates(candidates: list[str]) -> dict[str, dict[str, Any]]:
    """自选 vt_symbol → 行情行（缓存 / 全市场 / Redis 逐只补全）。"""
    by_vt: dict[str, dict[str, Any]] = {}
    by_symbol: dict[str, dict[str, Any]] = {}

    for row in quote_map().values():
        _ingest_quote_row(row, by_vt=by_vt, by_symbol=by_symbol)

    try:
        snapshot = load_screening_quote_snapshot()
        for row in snapshot.rows:
            _ingest_quote_row(dict(row), by_vt=by_vt, by_symbol=by_symbol)
    except MarketQuotesLoadError:
        pass

    missing_tf: list[str] = []
    for vt_symbol in candidates:
        if vt_symbol in by_vt:
            continue
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            continue
        if item.symbol in by_symbol:
            merged = dict(by_symbol[item.symbol])
            merged["vt_symbol"] = vt_symbol
            by_vt[vt_symbol] = merged
            continue
        missing_tf.append(item.tickflow_symbol)

    if missing_tf:
        try:
            quotes = RedisQuoteStore().get_quotes(missing_tf)
            for tf_symbol, quote in quotes.items():
                item = parse_tickflow_symbol(tf_symbol, quote.name)
                if item is None:
                    continue
                _ingest_quote_row(
                    {
                        "vt_symbol": item.vt_symbol,
                        "symbol": item.symbol,
                        "name": quote.name or item.name,
                        "last_price": quote.last_price,
                        "close": quote.last_price,
                        "change_pct": quote.change_pct,
                        "turnover_rate": quote.turnover_rate,
                        "volume": quote.volume,
                        "amount": quote.amount,
                    },
                    by_vt=by_vt,
                    by_symbol=by_symbol,
                )
        except Exception:
            pass

    result: dict[str, dict[str, Any]] = {}
    for vt_symbol in candidates:
        if vt_symbol in by_vt:
            result[vt_symbol] = by_vt[vt_symbol]
        else:
            item = parse_stock_symbol(vt_symbol)
            result[vt_symbol] = {
                "vt_symbol": vt_symbol,
                "symbol": item.symbol if item else vt_symbol.split(".")[0],
            }
    return result


def has_quote_data(row: QuoteRowLike) -> bool:
    merged = merge_row_quotes(row)
    return bool(
        merged.get("change_pct") not in (None, "")
        or float(merged.get("last_price") or merged.get("close") or 0) > 0
        or float(merged.get("amount") or 0) > 0
    )
