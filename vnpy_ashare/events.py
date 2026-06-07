"""应用级事件（看盘、回测导航等）。"""

from __future__ import annotations

from dataclasses import dataclass

EVENT_OPEN_BACKTEST = "eOpenBacktest"


@dataclass
class BacktestRequest:
    """从看盘页跳转策略回测时携带的上下文。"""

    vt_symbol: str
    source_page: str = ""
    name: str = ""
