"""雷达页共享数据模型与行情合并工具。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from vnpy_ashare.ai.context.store import get_market_quotes_cache
from vnpy_ashare.domain.symbols import parse_stock_symbol, parse_tickflow_symbol
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError


@dataclass(frozen=True)
class RadarRow:
    vt_symbol: str
    name: str
    symbol: str
    price: float | None
    change_pct: float | None
    metric_label: str
    metric_value: str
    sub_label: str
    sub_value: str


@dataclass(frozen=True)
class RadarCardData:
    card_id: str
    title: str
    subtitle: str
    rows: tuple[RadarRow, ...]
    empty_message: str
    updated_at: str
    run_id: str = ""
    detail_page_key: str = ""
    total_count: int = 0
    ai_hint: str = ""
    sector_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class RadarResonanceEntry:
    vt_symbol: str
    name: str
    symbol: str
    card_count: int
    card_titles: tuple[str, ...]
    price: float | None
    change_pct: float | None
    resonance_score: float = 0.0


def quote_map() -> dict[str, dict[str, Any]]:
    cached = get_market_quotes_cache()
    if not cached:
        return {}
    return {str(row.get("vt_symbol") or ""): row for row in cached if row.get("vt_symbol")}


def float_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def format_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.2f}%"


def merge_row_quotes(row: dict[str, Any]) -> dict[str, Any]:
    """合并行情缓存，补全 volume / amount / 现价等字段。"""
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    merged = dict(row)
    quote = quote_map().get(vt_symbol, {})
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
        if not merged.get(key):
            merged[key] = cached
    return merged


def _ingest_quote_row(
    row: dict[str, Any],
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


def quotes_for_vt_symbols(vt_symbols: list[str]) -> dict[str, dict[str, Any]]:
    """批量补全行情：内存缓存 → 全市场筛选快照 → Redis 逐只。"""
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
            from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore

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
    from vnpy_ashare.quotes.radar.radar_relative_strength import enrich_radar_row_relative_strength

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
        updated = replace(row, price=price, change_pct=change_pct)
    return enrich_radar_row_relative_strength(updated, merged)


def enrich_radar_rows(rows: tuple[RadarRow, ...]) -> tuple[RadarRow, ...]:
    """批量补全雷达行行情字段。"""
    if not rows:
        return rows
    quotes = quotes_for_vt_symbols([row.vt_symbol for row in rows])
    return tuple(enrich_radar_row(row, quotes.get(row.vt_symbol, {"vt_symbol": row.vt_symbol})) for row in rows)
