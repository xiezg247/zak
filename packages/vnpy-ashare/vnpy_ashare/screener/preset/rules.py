"""选股规则（行情 / Tushare 基本面）。

行情 preset 对 ``quotes`` 行排序/过滤；Tushare preset 对 ``daily_basic`` / ``moneyflow`` 行筛选。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRow, QuoteRowLike, coerce_quote_row, quote_row_copy
from vnpy_ashare.quotes.market.moneyflow_kind import enrich_moneyflow_row_with_kind
from vnpy_ashare.screener.data.screening_context import get_volume_ratio_map
from vnpy_ashare.screener.hard_filters import apply_screening_filters
from vnpy_ashare.screener.preset.presets import (
    SCREENER_CHANGE_TOP,
    SCREENER_CUSTOM,
    SCREENER_STRONG_UP,
    SCREENER_TURNOVER,
    SCREENER_VOLUME_RATIO,
    SCREENER_VOLUME_SURGE,
)

# Tushare daily_basic.total_mv 单位为万元；50 亿 = 500000 万元
MIN_TOTAL_MV_50YI = 500_000.0
STRONG_UP_MIN_CHANGE_PCT = 5.0


def _quote_liquidity_key(row: QuoteRowLike) -> float:
    """成交量优先；缺失时用成交额或总市值排序（盘后 daily_basic 常无 amount）。"""
    volume = float(row.get("volume") or 0)
    if volume > 0:
        return volume
    amount = float(row.get("amount") or 0)
    if amount > 0:
        return amount
    total_mv = float(row.get("total_mv") or row.get("circ_mv") or 0)
    if total_mv > 0:
        return total_mv
    return float(row.get("turnover_rate") or 0)


def apply_quote_preset(
    preset: str,
    quotes: Sequence[QuoteRowLike],
    *,
    top_n: int = 20,
    min_change_pct: float | None = None,
    max_change_pct: float | None = None,
    min_turnover: float | None = None,
) -> list[QuoteRow]:
    """对行情行应用 preset 规则，返回标准化结果行（最多 top_n 条）。"""
    preset = preset.strip()
    top_n = max(1, min(int(top_n or 20), 200))
    quotes = apply_screening_filters(quotes)

    if preset == SCREENER_CUSTOM:
        result = quotes
        if min_change_pct is not None:
            result = [q for q in result if q.get("change_pct", 0) >= min_change_pct]
        if max_change_pct is not None:
            result = [q for q in result if q.get("change_pct", 0) <= max_change_pct]
        if min_turnover is not None:
            result = [q for q in result if q.get("turnover_rate", 0) >= min_turnover]
        result = sorted(result, key=lambda q: q.get("change_pct", 0), reverse=True)
        return [_quote_row(q) for q in result[:top_n]]

    if preset == SCREENER_CHANGE_TOP:
        sorted_quotes = sorted(quotes, key=lambda q: q.get("change_pct", 0), reverse=True)
    elif preset == SCREENER_STRONG_UP:
        filtered = [q for q in quotes if float(q.get("change_pct") or 0) >= STRONG_UP_MIN_CHANGE_PCT]
        sorted_quotes = sorted(filtered, key=lambda q: q.get("change_pct", 0), reverse=True)
    elif preset == SCREENER_VOLUME_RATIO:
        volume_ratio_rows = _sort_by_volume_ratio(quotes)
        return [_quote_row(q) for q in volume_ratio_rows[:top_n]]
    elif preset == SCREENER_TURNOVER:
        sorted_quotes = sorted(quotes, key=lambda q: q.get("turnover_rate", 0), reverse=True)
    elif preset == SCREENER_VOLUME_SURGE:
        sorted_quotes = sorted(quotes, key=_quote_liquidity_key, reverse=True)
    else:
        return []
    return [_quote_row(q) for q in sorted_quotes[:top_n]]


def apply_low_pe(rows: Sequence[QuoteRowLike], *, top_n: int, max_pe_ttm: float = 15.0) -> list[QuoteRow]:
    """PE(TTM) 在 (0, max_pe_ttm) 内升序取 top_n。"""
    rows = apply_screening_filters(rows)
    filtered = [row for row in rows if row.get("pe_ttm", 0) > 0 and row.get("pe_ttm", 0) < max_pe_ttm]
    filtered.sort(key=lambda r: r.get("pe_ttm", 0))
    return [_fundamental_row(r) for r in filtered[:top_n]]


def apply_large_cap(
    rows: Sequence[QuoteRowLike],
    *,
    top_n: int,
    min_total_mv: float = MIN_TOTAL_MV_50YI,
) -> list[QuoteRow]:
    """总市值 ≥ min_total_mv（默认 50 亿）降序取 top_n。"""
    rows = apply_screening_filters(rows)
    filtered = [row for row in rows if row.get("total_mv", 0) >= min_total_mv]
    filtered.sort(key=lambda r: r.get("total_mv", 0), reverse=True)
    return [_fundamental_row(r) for r in filtered[:top_n]]


def apply_limit_up(rows: Sequence[QuoteRowLike], *, top_n: int) -> list[QuoteRow]:
    """涨停列表按连板次数降序取 top_n。"""
    rows = apply_screening_filters(rows)
    sorted_rows = sorted(rows, key=lambda r: float(r.get("limit_times") or 0), reverse=True)
    return [_limit_up_row(r) for r in sorted_rows[:top_n]]


def _sort_by_volume_ratio(quotes: Sequence[QuoteRowLike]) -> list[QuoteRow]:
    ratio_map = get_volume_ratio_map()
    enriched: list[QuoteRow] = []
    for row in quotes:
        vt_symbol = str(row.get("vt_symbol") or "")
        ratio = float(ratio_map.get(vt_symbol) or row.get("volume_ratio") or 0)
        if ratio <= 0:
            continue
        enriched.append(quote_row_copy(row, volume_ratio=ratio))
    enriched.sort(key=lambda item: float(item.get("volume_ratio") or 0), reverse=True)
    return enriched


def apply_moneyflow_in(rows: Sequence[QuoteRowLike], *, top_n: int) -> list[QuoteRow]:
    """主力净流入 > 0 降序取 top_n。"""
    rows = apply_screening_filters(rows)
    filtered = [row for row in rows if row.get("net_mf_amount", 0) > 0]
    filtered.sort(key=lambda r: r.get("net_mf_amount", 0), reverse=True)
    return [_moneyflow_row(r) for r in filtered[:top_n]]


_DISPLAY_FUNDAMENTAL_KEYS = ("close", "pe_ttm", "pb", "total_mv", "circ_mv", "trade_date")


def _quote_row(row: QuoteRowLike) -> QuoteRow:
    last_price = row.get("last_price") or row.get("close") or 0
    close = row.get("close") or last_price or 0
    updates: dict[str, Any] = {
        "symbol": row.get("symbol", ""),
        "name": row.get("name", ""),
        "vt_symbol": row.get("vt_symbol", ""),
        "last_price": last_price or close,
        "close": close,
        "prev_close": row.get("prev_close", 0),
        "open_price": row.get("open_price", 0),
        "high_price": row.get("high_price", 0),
        "low_price": row.get("low_price", 0),
        "change_pct": row.get("change_pct", 0),
        "turnover_rate": row.get("turnover_rate", 0),
        "volume": row.get("volume", 0),
        "amount": row.get("amount", 0),
        "volume_ratio": row.get("volume_ratio", 0),
        "source": row.get("source", "quote"),
    }
    for key in _DISPLAY_FUNDAMENTAL_KEYS:
        value = row.get(key)
        if value not in (None, ""):
            updates[key] = value
    return quote_row_copy(row, **updates)


def _limit_up_row(row: QuoteRowLike) -> QuoteRow:
    vt_symbol = str(row.get("vt_symbol") or "")
    symbol = vt_symbol.split(".")[0] if vt_symbol else ""
    return quote_row_copy(
        row,
        symbol=symbol,
        name=str(row.get("name") or ""),
        vt_symbol=vt_symbol,
        limit_times=float(row.get("limit_times") or 0),
        limit=str(row.get("limit") or ""),
        trade_date=str(row.get("trade_date") or ""),
        source="tushare",
    )


def _fundamental_row(row: QuoteRowLike) -> QuoteRow:
    return quote_row_copy(
        row,
        symbol=str(row.get("symbol") or ""),
        name=str(row.get("name") or ""),
        vt_symbol=str(row.get("vt_symbol") or ""),
        close=float(row.get("close") or 0),
        pe_ttm=float(row.get("pe_ttm") or 0),
        pb=float(row.get("pb") or 0),
        total_mv=float(row.get("total_mv") or 0),
        circ_mv=float(row.get("circ_mv") or 0),
        turnover_rate=float(row.get("turnover_rate") or 0),
        trade_date=str(row.get("trade_date") or ""),
        source=str(row.get("source") or "tushare"),
    )


def _moneyflow_row(row: QuoteRowLike) -> QuoteRow:
    payload: dict[str, Any] = {
        "symbol": row.get("symbol", ""),
        "name": row.get("name", ""),
        "vt_symbol": row.get("vt_symbol", ""),
        "net_mf_amount": row.get("net_mf_amount", 0),
        "buy_elg_amount": row.get("buy_elg_amount", 0),
        "sell_elg_amount": row.get("sell_elg_amount", 0),
        "buy_lg_amount": row.get("buy_lg_amount", 0),
        "sell_lg_amount": row.get("sell_lg_amount", 0),
        "buy_md_amount": row.get("buy_md_amount", 0),
        "sell_md_amount": row.get("sell_md_amount", 0),
        "change_pct": row.get("change_pct", row.get("pct_chg", 0)),
        "turnover_rate": row.get("turnover_rate", 0),
        "trade_date": row.get("trade_date", ""),
        "moneyflow_source": row.get("moneyflow_source", "tushare"),
        "source": "tushare",
    }
    if row.get("moneyflow_proxy"):
        payload["moneyflow_proxy"] = row["moneyflow_proxy"]
    return coerce_quote_row(enrich_moneyflow_row_with_kind(payload))
