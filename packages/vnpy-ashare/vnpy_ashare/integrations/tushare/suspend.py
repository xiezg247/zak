"""Tushare 停复牌数据拉取。"""

from __future__ import annotations

from datetime import date
from typing import Any

from vnpy_ashare.domain.symbols.stock import ts_code_to_vt_symbol
from vnpy_ashare.integrations.tushare.client import get_tushare_pro


def fetch_suspend_d(trade_date: date, *, suspend_type: str = "S") -> list[dict[str, str]]:
    """拉取指定交易日停复牌记录（默认仅停牌 S）。"""
    pro = get_tushare_pro()
    frame = pro.suspend_d(
        trade_date=trade_date.strftime("%Y%m%d"),
        suspend_type=suspend_type,
        fields="ts_code,trade_date,suspend_type",
    )
    if frame is None or frame.empty:
        return []

    rows: list[dict[str, str]] = []
    for record in frame.to_dict(orient="records"):
        ts_code = str(record.get("ts_code") or "").strip()
        vt_symbol = ts_code_to_vt_symbol(ts_code)
        if not vt_symbol or "." not in vt_symbol:
            continue
        symbol, exchange = vt_symbol.rsplit(".", 1)
        cal_date = _normalize_cal_date(record.get("trade_date"), fallback=trade_date)
        row_type = str(record.get("suspend_type") or suspend_type).strip().upper()
        if row_type != "S":
            continue
        rows.append(
            {
                "symbol": symbol,
                "exchange": exchange,
                "cal_date": cal_date,
                "suspend_type": row_type,
            }
        )
    return rows


def _normalize_cal_date(value: Any, *, fallback: date) -> str:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) == 10 and text[4] == "-":
        return text
    return fallback.isoformat()
