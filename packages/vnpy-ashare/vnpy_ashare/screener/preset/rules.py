"""选股规则（行情 / Tushare 基本面）。

行情 preset 对 ``quotes`` 行排序/过滤；Tushare preset 对 ``daily_basic`` / ``moneyflow`` 行筛选。
"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.screener.hard_filters import apply_screening_filters
from vnpy_ashare.screener.preset.presets import (
    SCREENER_CHANGE_TOP,
    SCREENER_CUSTOM,
    SCREENER_TURNOVER,
    SCREENER_VOLUME_SURGE,
)

# Tushare daily_basic.total_mv 单位为万元；50 亿 = 500000 万元
MIN_TOTAL_MV_50YI = 500_000.0


def _quote_liquidity_key(row: dict[str, Any]) -> float:
    """成交量优先；缺失时用成交额排序（部分行情源 volume 恒为 0）。"""
    volume = float(row.get("volume") or 0)
    if volume > 0:
        return volume
    return float(row.get("amount") or 0)


def apply_quote_preset(
    preset: str,
    quotes: list[dict[str, Any]],
    *,
    top_n: int = 20,
    min_change_pct: float | None = None,
    max_change_pct: float | None = None,
    min_turnover: float | None = None,
) -> list[dict[str, Any]]:
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
    elif preset == SCREENER_TURNOVER:
        sorted_quotes = sorted(quotes, key=lambda q: q.get("turnover_rate", 0), reverse=True)
    elif preset == SCREENER_VOLUME_SURGE:
        sorted_quotes = sorted(quotes, key=_quote_liquidity_key, reverse=True)
    else:
        return []
    return [_quote_row(q) for q in sorted_quotes[:top_n]]


def apply_low_pe(rows: list[dict[str, Any]], *, top_n: int, max_pe_ttm: float = 15.0) -> list[dict[str, Any]]:
    """PE(TTM) 在 (0, max_pe_ttm) 内升序取 top_n。"""
    rows = apply_screening_filters(rows)
    filtered = [row for row in rows if row.get("pe_ttm", 0) > 0 and row.get("pe_ttm", 0) < max_pe_ttm]
    filtered.sort(key=lambda r: r.get("pe_ttm", 0))
    return [_fundamental_row(r) for r in filtered[:top_n]]


def apply_large_cap(
    rows: list[dict[str, Any]],
    *,
    top_n: int,
    min_total_mv: float = MIN_TOTAL_MV_50YI,
) -> list[dict[str, Any]]:
    """总市值 ≥ min_total_mv（默认 50 亿）降序取 top_n。"""
    rows = apply_screening_filters(rows)
    filtered = [row for row in rows if row.get("total_mv", 0) >= min_total_mv]
    filtered.sort(key=lambda r: r.get("total_mv", 0), reverse=True)
    return [_fundamental_row(r) for r in filtered[:top_n]]


def apply_moneyflow_in(rows: list[dict[str, Any]], *, top_n: int) -> list[dict[str, Any]]:
    """主力净流入 > 0 降序取 top_n。"""
    rows = apply_screening_filters(rows)
    filtered = [row for row in rows if row.get("net_mf_amount", 0) > 0]
    filtered.sort(key=lambda r: r.get("net_mf_amount", 0), reverse=True)
    return [_moneyflow_row(r) for r in filtered[:top_n]]


def _quote_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": row.get("symbol", ""),
        "name": row.get("name", ""),
        "vt_symbol": row.get("vt_symbol", ""),
        "last_price": row.get("last_price", 0),
        "prev_close": row.get("prev_close", 0),
        "open_price": row.get("open_price", 0),
        "high_price": row.get("high_price", 0),
        "low_price": row.get("low_price", 0),
        "change_pct": row.get("change_pct", 0),
        "turnover_rate": row.get("turnover_rate", 0),
        "volume": row.get("volume", 0),
        "amount": row.get("amount", 0),
        "source": "quote",
    }


def _fundamental_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": row.get("symbol", ""),
        "name": row.get("name", ""),
        "vt_symbol": row.get("vt_symbol", ""),
        "close": row.get("close", 0),
        "pe_ttm": row.get("pe_ttm", 0),
        "pb": row.get("pb", 0),
        "total_mv": row.get("total_mv", 0),
        "circ_mv": row.get("circ_mv", 0),
        "turnover_rate": row.get("turnover_rate", 0),
        "trade_date": row.get("trade_date", ""),
        "source": row.get("source", "tushare"),
    }


def _moneyflow_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": row.get("symbol", ""),
        "name": row.get("name", ""),
        "vt_symbol": row.get("vt_symbol", ""),
        "net_mf_amount": row.get("net_mf_amount", 0),
        "buy_elg_amount": row.get("buy_elg_amount", 0),
        "sell_elg_amount": row.get("sell_elg_amount", 0),
        "trade_date": row.get("trade_date", ""),
        "source": "tushare",
    }
