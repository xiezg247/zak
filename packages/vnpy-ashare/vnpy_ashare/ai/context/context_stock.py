"""从 AiContextData 解析笔记/跳转用标的。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.config.runtime import _CN_NAME_TO_EXCHANGE
from vnpy_common.ai.protocol import AiContextData


def resolve_exchange_label(label: str) -> Exchange | None:
    """将 context 中的 exchange 字段解析为 Exchange（支持 SSE / 上交所 等）。"""
    text = str(label or "").strip()
    if not text:
        return None
    if text in Exchange.__members__:
        return Exchange[text]
    mapped = _CN_NAME_TO_EXCHANGE.get(text)
    if mapped is not None:
        return mapped
    try:
        return Exchange(text)
    except ValueError:
        return None


def context_stock_from_ai(data: AiContextData) -> tuple[str, Exchange, str] | None:
    """从 AI 上下文解析 (symbol, exchange, name)；无法解析时返回 None。"""
    symbol = str(data.symbol or "").strip()
    exchange = resolve_exchange_label(str(data.exchange or ""))
    if not symbol or exchange is None:
        return None
    return symbol, exchange, str(data.name or "").strip()
