"""TickFlow 数据结构类型。"""

from __future__ import annotations

from typing import TypedDict


class TickflowKlineRow(TypedDict, total=False):
    """TickFlow K 线 DataFrame 行字段。"""

    timestamp: int
    trade_time: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
