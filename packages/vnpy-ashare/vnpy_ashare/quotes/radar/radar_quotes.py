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
    已是 dict 时就地浅拷贝后补字段，避免多余 ``coerce_quote_row().to_dict()``。
    """
    if isinstance(row, ScreenerResultRow):
        merged = row.to_dict()
    elif isinstance(row, QuoteRow):
        merged = row.to_dict()
    elif isinstance(row, Mapping):
        merged = dict(row)
    else:
        merged = coerce_quote_row(row).to_dict()
    vt_symbol = str(merged.get("vt_symbol") or "").strip()
    quote = quote_map().get(vt_symbol)
    if quote is None:
        return merged
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
        cached = quote.get(key)
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


def _ingest_redis_quotes(
    tf_symbols: list[str],
    *,
    by_vt: dict[str, dict[str, Any]],
    by_symbol: dict[str, dict[str, Any]],
) -> None:
    if not tf_symbols:
        return
    try:
        quotes = get_redis_quote_store().get_quotes(tf_symbols)
    except Exception:
        return
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


def _missing_vt_symbols(
    vt_symbols: list[str],
    by_vt: dict[str, dict[str, Any]],
) -> list[str]:
    return [vt for vt in vt_symbols if vt not in by_vt]


def _fill_from_quote_map(
    vt_symbols: list[str],
    *,
    by_vt: dict[str, dict[str, Any]],
    by_symbol: dict[str, dict[str, Any]],
) -> None:
    """按需从进程内行情缓存取请求标的（O(K)，禁止全表 ingest）。"""
    cache = quote_map()
    for vt_symbol in vt_symbols:
        if vt_symbol in by_vt:
            continue
        row = cache.get(vt_symbol)
        if row is not None:
            _ingest_quote_row(row, by_vt=by_vt, by_symbol=by_symbol)


def _fill_from_snapshot(
    vt_symbols: list[str],
    *,
    by_vt: dict[str, dict[str, Any]],
    by_symbol: dict[str, dict[str, Any]],
) -> None:
    """快照中仅 ingest 仍缺失的请求标的。

    有活跃 ScreeningContext 时走 vt 索引 O(K)；否则单次扫描只 ingest 命中行。
    """
    missing = _missing_vt_symbols(vt_symbols, by_vt)
    if not missing:
        return

    from vnpy_ashare.screener.data.screening_context_registry import get_screening_context

    ctx = get_screening_context()
    if ctx is not None and getattr(ctx, "_snapshot_loaded", False) and getattr(ctx, "_snapshot", None) is not None:
        for vt_symbol in missing:
            if vt_symbol in by_vt:
                continue
            row = ctx.get_quote_row_by_vt(vt_symbol)
            if row is not None:
                _ingest_quote_row(row, by_vt=by_vt, by_symbol=by_symbol)
        return

    wanted_vt = set(missing)
    wanted_symbols: set[str] = set()
    for vt_symbol in missing:
        item = parse_stock_symbol(vt_symbol)
        if item is not None:
            wanted_symbols.add(item.symbol)
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return
    for row in snapshot.rows:
        vt = str(row.get("vt_symbol") or "").strip()
        symbol = str(row.get("symbol") or "").strip()
        if vt in wanted_vt or (symbol and symbol in wanted_symbols):
            _ingest_quote_row(row, by_vt=by_vt, by_symbol=by_symbol)


def _apply_symbol_fallback(
    vt_symbols: list[str],
    *,
    by_vt: dict[str, dict[str, Any]],
    by_symbol: dict[str, dict[str, Any]],
) -> list[str]:
    """用同代码不同交易所映射补洞；返回仍缺失的 tickflow 代码。"""
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
    return missing_tf


def quotes_for_vt_symbols(vt_symbols: list[str]) -> dict[str, dict[str, Any]]:
    """批量补全行情：盘中优先 Redis → 按需内存缓存 → 按需快照 → Redis 补洞。

    仅对请求的 K 个 vt_symbol 取数，避免为少量标的扫描全市场 ~5000 行。
    """
    by_vt: dict[str, dict[str, Any]] = {}
    by_symbol: dict[str, dict[str, Any]] = {}
    live_session = is_ashare_trading_session()

    if live_session and vt_symbols:
        tf_symbols: list[str] = []
        for vt_symbol in vt_symbols:
            item = parse_stock_symbol(vt_symbol)
            if item is not None:
                tf_symbols.append(item.tickflow_symbol)
        _ingest_redis_quotes(tf_symbols, by_vt=by_vt, by_symbol=by_symbol)

    _fill_from_quote_map(vt_symbols, by_vt=by_vt, by_symbol=by_symbol)
    _fill_from_snapshot(vt_symbols, by_vt=by_vt, by_symbol=by_symbol)
    missing_tf = _apply_symbol_fallback(vt_symbols, by_vt=by_vt, by_symbol=by_symbol)

    if missing_tf:
        _ingest_redis_quotes(missing_tf, by_vt=by_vt, by_symbol=by_symbol)
        _apply_symbol_fallback(vt_symbols, by_vt=by_vt, by_symbol=by_symbol)

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
