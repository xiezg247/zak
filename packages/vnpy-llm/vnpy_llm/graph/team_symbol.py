"""投研团队模式：股票代码解析与上下文回退。"""

from __future__ import annotations

import re

from vnpy.trader.constant import Exchange

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.config import _CN_NAME_TO_EXCHANGE

_SYMBOL_PATTERN = re.compile(r"(\d{6}(?:\.(?:SSE|SZSE|BSE|SH|SZ|BJ))?)", re.IGNORECASE)


def normalize_symbol_code(raw: str) -> str | None:
    """将各类代码格式规范为 vt_symbol（如 600519.SSE）。"""
    text = raw.strip().upper()
    if not text:
        return None
    item = parse_stock_symbol(text)
    if item is not None:
        return str(item.vt_symbol)
    return None


def resolve_team_symbol(
    *,
    user_text: str,
    context_symbol: str = "",
    context_exchange: str = "",
) -> str | None:
    """从用户消息或终端选中标的解析团队分析目标代码。"""
    match = _SYMBOL_PATTERN.search(user_text)
    if match:
        resolved = normalize_symbol_code(match.group(1))
        if resolved:
            return resolved

    symbol = (context_symbol or "").strip()
    if not symbol:
        return None

    exchange_label = (context_exchange or "").strip()
    if exchange_label:
        exchange = _CN_NAME_TO_EXCHANGE.get(exchange_label)
        if exchange is None:
            try:
                exchange = Exchange(exchange_label)
            except ValueError:
                exchange = None
        if exchange is not None:
            resolved = normalize_symbol_code(f"{symbol}.{exchange.value}")
            if resolved:
                return resolved
        resolved = normalize_symbol_code(f"{symbol}.{exchange_label}")
        if resolved:
            return resolved

    return normalize_symbol_code(symbol)
