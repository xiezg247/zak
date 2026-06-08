"""AI 会话共享上下文（终端 UI → Skills 工具）。"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from vnpy_ashare.ai.context import AiContextData

_lock = threading.Lock()
_ai_context = AiContextData()
_backtest_summary: dict[str, Any] | None = None


@dataclass
class BacktestSummary:
    """最近一次回测摘要。"""

    strategy: str
    vt_symbol: str
    interval: str
    start: str
    end: str
    statistics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "vt_symbol": self.vt_symbol,
            "interval": self.interval,
            "start": self.start,
            "end": self.end,
            "statistics": self.statistics,
        }


def set_ai_context(data: AiContextData) -> None:
    global _ai_context
    with _lock:
        _ai_context = data


def get_ai_context() -> AiContextData:
    with _lock:
        return _ai_context


def set_backtest_summary(summary: BacktestSummary | None) -> None:
    global _backtest_summary
    with _lock:
        _backtest_summary = summary.to_dict() if summary else None


def get_backtest_summary() -> dict[str, Any] | None:
    with _lock:
        return dict(_backtest_summary) if _backtest_summary else None


def clear_session_context() -> None:
    global _ai_context, _backtest_summary
    with _lock:
        _ai_context = AiContextData()
        _backtest_summary = None
