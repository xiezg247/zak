"""雷达页共享数据模型与行情合并工具。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from vnpy_ashare.domain.core.numbers import float_or_none
from vnpy_ashare.domain.market.quote_row import QuoteRow, coerce_quote_row
from vnpy_ashare.domain.radar.card import RadarCardData, RadarResonanceEntry, RadarRow
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.domain.symbols.stock import parse_stock_symbol, parse_tickflow_symbol
from vnpy_ashare.quotes.core.quote_rows import quote_rows_by_vt_symbol
from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore
from vnpy_ashare.quotes.radar.radar_relative_strength import enrich_radar_row_relative_strength
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError

__all__ = [
    "RadarCardData",
    "RadarResonanceEntry",
    "RadarRow",
    "enrich_radar_rows",
    "merge_row_quotes",
    "quote_map",
    "resolve_radar_rows",
]


def quote_map() -> dict[str, QuoteRow]:
    """vt_symbol → 行情行（读进程内缓存）。"""
    return quote_rows_by_vt_symbol()


def merge_row_quotes(row: QuoteRow | ScreenerResultRow | Mapping[str, Any]) -> dict[str, Any]:
    """合并行情缓存，补全 volume / amount / 现价等字段。"""
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
        if not merged.get(key):
            merged[key] = cached
    return merged


def _ingest_quote_row(
    row: QuoteRow | Mapping[str, Any],
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
    """批量补全行情：内存缓存 → 全市场筛选快照 → Redis 逐只。"""
    by_vt: dict[str, dict[str, Any]] = {}
    by_symbol: dict[str, dict[str, Any]] = {}

    for row in quote_map().values():
        _ingest_quote_row(row, by_vt=by_vt, by_symbol=by_symbol)

    try:
        snapshot = load_screening_quote_snapshot()
        for row in snapshot.rows:
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


def enrich_radar_row(row: RadarRow, quote: dict[str, Any]) -> RadarRow:
    """用全市场行情补全 RadarRow 的现价、涨幅与相对强度副标题。"""

    merged = merge_row_quotes(quote)
    price = float_or_none(merged.get("last_price") or merged.get("close"))
    if price is None:
        price = row.price
    change_pct = float_or_none(
        merged.get("change_pct") or quote.get("change_pct") or quote.get("pct_chg"),
    )
    if change_pct is None:
        change_pct = row.change_pct
    updated = row
    if price != row.price or change_pct != row.change_pct:
        updated = row.model_copy(update={"price": price, "change_pct": change_pct})
    return enrich_radar_row_relative_strength(updated, merged)


def enrich_radar_rows(rows: tuple[RadarRow, ...]) -> tuple[RadarRow, ...]:
    """批量补全雷达行行情字段。"""
    if not rows:
        return rows
    quotes = quotes_for_vt_symbols([row.vt_symbol for row in rows])
    return tuple(enrich_radar_row(row, quotes.get(row.vt_symbol, {"vt_symbol": row.vt_symbol})) for row in rows)


def radar_row_to_cache_dict(row: RadarRow) -> dict[str, Any]:
    """RadarRow → SQLite 缓存 JSON 条目。"""
    payload: dict[str, Any] = {
        "vt_symbol": row.vt_symbol,
        "name": row.name,
        "symbol": row.symbol,
        "metric_label": row.metric_label,
        "metric_value": row.metric_value,
        "sub_label": row.sub_label,
        "sub_value": row.sub_value,
    }
    if row.price is not None:
        payload["last_close"] = row.price
    if row.change_pct is not None:
        payload["change_pct"] = row.change_pct
    return payload


def radar_row_from_cache_dict(raw: dict[str, Any], *, quote: dict[str, Any] | None = None) -> RadarRow:
    """SQLite 缓存 JSON 条目 → RadarRow（可选合并实时行情）。"""
    vt_symbol = str(raw.get("vt_symbol") or "").strip()
    base = quote if quote is not None else {"vt_symbol": vt_symbol}
    row = RadarRow(
        vt_symbol=vt_symbol,
        name=str(raw.get("name") or ""),
        symbol=str(raw.get("symbol") or ""),
        price=float_or_none(raw.get("last_close")),
        change_pct=float_or_none(raw.get("change_pct")),
        metric_label=str(raw.get("metric_label") or ""),
        metric_value=str(raw.get("metric_value") or ""),
        sub_label=str(raw.get("sub_label") or ""),
        sub_value=str(raw.get("sub_value") or ""),
    )
    return enrich_radar_row(row, base)
