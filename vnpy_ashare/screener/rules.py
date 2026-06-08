"""选股规则（行情 / Tushare 基本面）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.screener.presets import (
    SCREENER_CHANGE_TOP,
    SCREENER_CUSTOM,
    SCREENER_LARGE_CAP,
    SCREENER_LOW_PE,
    SCREENER_MONEYFLOW_IN,
    SCREENER_TURNOVER,
    SCREENER_VOLUME_SURGE,
    list_builtin_preset_names,
)

# Tushare daily_basic.total_mv 单位为万元；50 亿 = 500000 万元
MIN_TOTAL_MV_50YI = 500_000.0


def apply_quote_preset(
    preset: str,
    quotes: list[dict[str, Any]],
    *,
    top_n: int = 20,
    min_change_pct: float | None = None,
    max_change_pct: float | None = None,
    min_turnover: float | None = None,
) -> list[dict[str, Any]]:
    preset = preset.strip()
    top_n = max(1, min(int(top_n or 20), 200))

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
        sorted_quotes = sorted(quotes, key=lambda q: q.get("volume", 0), reverse=True)
    else:
        return []
    return [_quote_row(q) for q in sorted_quotes[:top_n]]


def apply_low_pe(rows: list[dict[str, Any]], *, top_n: int, max_pe_ttm: float = 15.0) -> list[dict[str, Any]]:
    filtered = [
        row for row in rows
        if row.get("pe_ttm", 0) > 0 and row.get("pe_ttm", 0) < max_pe_ttm
    ]
    filtered.sort(key=lambda r: r.get("pe_ttm", 0))
    return [_fundamental_row(r) for r in filtered[:top_n]]


def apply_large_cap(
    rows: list[dict[str, Any]],
    *,
    top_n: int,
    min_total_mv: float = MIN_TOTAL_MV_50YI,
) -> list[dict[str, Any]]:
    filtered = [row for row in rows if row.get("total_mv", 0) >= min_total_mv]
    filtered.sort(key=lambda r: r.get("total_mv", 0), reverse=True)
    return [_fundamental_row(r) for r in filtered[:top_n]]


def apply_moneyflow_in(rows: list[dict[str, Any]], *, top_n: int) -> list[dict[str, Any]]:
    filtered = [row for row in rows if row.get("net_mf_amount", 0) > 0]
    filtered.sort(key=lambda r: r.get("net_mf_amount", 0), reverse=True)
    return [_moneyflow_row(r) for r in filtered[:top_n]]


def _quote_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": row.get("symbol", ""),
        "name": row.get("name", ""),
        "vt_symbol": row.get("vt_symbol", ""),
        "last_price": row.get("last_price", 0),
        "change_pct": row.get("change_pct", 0),
        "turnover_rate": row.get("turnover_rate", 0),
        "volume": row.get("volume", 0),
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
        "source": "tushare",
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
