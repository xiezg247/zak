"""A 股代码解析（AI 工具共用）。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange
from vnpy.trader.utility import extract_vt_symbol

from vnpy_ashare.domain.models import StockItem, parse_tickflow_symbol


def parse_stock_symbol(symbol: str) -> StockItem | None:
    """
    解析 A 股代码，支持：
    - 600519.SSE / 600519.SZSE / 600519.BSE
    - 600519.SH / 600519.SZ / 600519.BJ
    - 600519（按首位推断交易所）
    """
    text = symbol.strip()
    if not text:
        return None

    if "." in text:
        code, suffix = text.rsplit(".", 1)
        suffix_upper = suffix.upper()
        if suffix_upper in {"SH", "SZ", "BJ"}:
            return parse_tickflow_symbol(text)
        try:
            sym, exchange = extract_vt_symbol(text)
            return StockItem(symbol=sym, exchange=exchange)
        except ValueError:
            return None

    if len(text) == 6 and text.isdigit():
        if text.startswith(("5", "6", "9")):
            return StockItem(symbol=text, exchange=Exchange.SSE)
        if text.startswith(("0", "3")):
            return StockItem(symbol=text, exchange=Exchange.SZSE)
        if text.startswith(("4", "8")):
            return StockItem(symbol=text, exchange=Exchange.BSE)
    return None
