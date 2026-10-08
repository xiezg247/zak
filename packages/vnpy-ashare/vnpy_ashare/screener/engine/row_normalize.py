"""选股共用的行情行规范化与排序键（engine / preset / 雷达发现共用）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRow, QuoteRowLike, coerce_quote_row, quote_row_copy
from vnpy_ashare.quotes.market.moneyflow_kind import enrich_moneyflow_row_with_kind

_DISPLAY_FUNDAMENTAL_KEYS = ("close", "pe_ttm", "pb", "total_mv", "circ_mv", "trade_date")


def quote_liquidity_key(row: QuoteRowLike) -> float:
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


def normalize_quote_row(row: QuoteRowLike) -> QuoteRow:
    """统一 last_price/close，并保留展示用基本面字段。"""
    last_price = row.get("last_price") or row.get("close") or 0
    close = row.get("close") or last_price or 0
    updates: dict[str, Any] = {
        "symbol": row.get("symbol", ""),
        "name": row.get("name", ""),
        "vt_symbol": row.get("vt_symbol", ""),
        "last_price": last_price or close,
        "close": close,
        "prev_close": float(row.get("prev_close") or 0),
        "open_price": float(row.get("open_price") or 0),
        "high_price": float(row.get("high_price") or 0),
        "low_price": float(row.get("low_price") or 0),
        "change_pct": float(row.get("change_pct") or 0),
        "turnover_rate": float(row.get("turnover_rate") or 0),
        "volume": float(row.get("volume") or 0),
        "amount": float(row.get("amount") or 0),
        "volume_ratio": float(row.get("volume_ratio") or 0),
        "source": row.get("source", "quote"),
    }
    for key in _DISPLAY_FUNDAMENTAL_KEYS:
        value = row.get(key)
        if value not in (None, ""):
            updates[key] = value
    return quote_row_copy(row, **updates)


def normalize_moneyflow_row(row: QuoteRowLike) -> QuoteRow:
    """资金流行规范化，并补齐 flow_kind。"""
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
        "change_pct": float(row.get("change_pct") or row.get("pct_chg") or 0),
        "turnover_rate": row.get("turnover_rate", 0),
        "trade_date": row.get("trade_date", ""),
        "moneyflow_source": row.get("moneyflow_source", "tushare"),
        "source": "tushare",
    }
    if row.get("moneyflow_proxy"):
        payload["moneyflow_proxy"] = row["moneyflow_proxy"]
    return coerce_quote_row(enrich_moneyflow_row_with_kind(payload))

