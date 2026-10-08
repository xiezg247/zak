"""雷达行情合并与批量拉取。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRow, QuoteRowLike, coerce_quote_row
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.domain.symbols.stock import parse_stock_symbol, parse_tickflow_symbol
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.quotes.core.quote_rows import quote_rows_by_vt_symbol
from vnpy_ashare.quotes.core.redis_store import get_redis_quote_store
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError

__all__ = [
    "merge_row_quotes",
    "quote_map",
    "quotes_for_vt_symbols",
]

_LIVE_QUOTE_FIELDS = frozenset(
    {
        "last_price",
        "close",
        "change_pct",
        "volume",
        "amount",
        "turnover_rate",
        "volume_ratio",
        "net_mf_amount",
    }
)


def quote_map() -> dict[str, QuoteRow]:
    """vt_symbol → 行情行（读进程内缓存）。"""
    return quote_rows_by_vt_symbol()


def merge_row_quotes(
    row: QuoteRowLike | ScreenerResultRow | Mapping[str, Any],
    *,
    prefer_row: bool = False,
) -> dict[str, Any]:
    """合并行情缓存，补全 volume / amount / 现价等字段。

    ``prefer_row=True`` 时盘中保留行内已有现价/涨幅（用于已走 Redis 的 enrich 路径）。
    """
    if isinstance(row, ScreenerResultRow):
        payload = row.to_dict()
    elif isinstance(row, QuoteRow):
        payload = row.to_dict()
    else:
        payload = dict(row)
    vt_symbol = str(payload.get("vt_symbol") or "").strip()
    merged = coerce_quote_row(payload).to_dict()
    quote = quote_map().get(vt_symbol)
    if quote is None:
        return merged
    quote_dict = quote.to_dict()
    live_session = is_ashare_trading_session()
    for key in (
        "volume",
        "amount",
        "change_pct",
        "last_price",
        "close",
        "turnover_rate",
        "volume_ratio",
        "net_mf_amount",
        "name",
    ):
        cached = quote_dict.get(key)
        if cached in (None, "", 0, 0.0):
            continue
        if live_session and key in _LIVE_QUOTE_FIELDS:
            if prefer_row and merged.get(key):
                continue
            if cached not in (None, "", 0, 0.0):
                merged[key] = cached
        elif not merged.get(key):
            merged[key] = cached
    return merged


def _ingest_quote_row(
    row: QuoteRowLike | Mapping[str, Any],
    *,
    by_vt: dict[str, dict[str, Any]],
    by_symbol: dict[str, dict[str, Any]],
) -> None:
    payload = coerce_quote_row(row).to_dict()
    vt_symbol = str(payload.get("vt_symbol") or "").strip()
    symbol = str(payload.get("symbol") or "").strip()
    if not vt_symbol and symbol:
        item = parse_stock_symbol(symbol)
        if item is not None:
            vt_symbol = item.vt_symbol
            payload = dict(payload)
            payload["vt_symbol"] = vt_symbol
    if vt_symbol:
        by_vt[vt_symbol] = dict(payload)
    if symbol:
        by_symbol[symbol] = dict(payload)


def quotes_for_vt_symbols(vt_symbols: list[str]) -> dict[str, dict[str, Any]]:
    """批量补全行情：盘中优先 Redis 实时 → 内存缓存 → 全市场快照。"""
    by_vt: dict[str, dict[str, Any]] = {}
    by_symbol: dict[str, dict[str, Any]] = {}
    live_session = is_ashare_trading_session()

    if live_session and vt_symbols:
        tf_symbols: list[str] = []
        for vt_symbol in vt_symbols:
            item = parse_stock_symbol(vt_symbol)
            if item is not None:
                tf_symbols.append(item.tickflow_symbol)
        if tf_symbols:
            try:
                quotes = get_redis_quote_store().get_quotes(tf_symbols)
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

    for row in quote_map().values():
        if live_session:
            vt = str(row.get("vt_symbol") or "").strip()
            if vt and vt in by_vt:
                continue
        _ingest_quote_row(row, by_vt=by_vt, by_symbol=by_symbol)

    try:
        snapshot = load_screening_quote_snapshot()
        for row in snapshot.rows:
            if live_session:
                vt = str(row.get("vt_symbol") or "").strip()
                if vt and vt in by_vt:
                    continue
            _ingest_quote_row(row, by_vt=by_vt, by_symbol=by_symbol)
    except MarketQuotesLoadError:
        pass

    missing_tf: list[str] = []
    for vt_symbol in vt_symbols:
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

    if missing_tf and not live_session:
        try:
            quotes = get_redis_quote_store().get_quotes(missing_tf)
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
    for vt_symbol in vt_symbols:
        if vt_symbol in by_vt:
            result[vt_symbol] = by_vt[vt_symbol]
        else:
            item = parse_stock_symbol(vt_symbol)
            result[vt_symbol] = {
                "vt_symbol": vt_symbol,
                "symbol": item.symbol if item else vt_symbol.split(".")[0],
            }
    return result
