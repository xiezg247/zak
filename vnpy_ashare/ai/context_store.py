"""AI 会话内存存储（线程安全）；业务代码请经 Service 访问。"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from vnpy_ashare.ai.context import AiContextData

_lock = threading.Lock()
_listeners: list[Callable[[AiContextData], None]] = []
_ai_context = AiContextData()
_backtest_summary: dict[str, Any] | None = None
_market_quotes: list[dict[str, Any]] = []


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


@dataclass
class ScreeningResultContext:
    condition: str
    count: int
    updated_at: str | None
    rows: list[dict[str, Any]]


_screening_result: ScreeningResultContext | None = None
_diagnose_result: dict[str, Any] | None = None


def register_context_listener(callback: Callable[[AiContextData], None]) -> None:
    with _lock:
        if callback not in _listeners:
            _listeners.append(callback)


def set_ai_context(data: AiContextData) -> None:
    global _ai_context
    with _lock:
        _ai_context = data
        listeners = list(_listeners)
    for listener in listeners:
        try:
            listener(data)
        except Exception:
            pass


def get_ai_context() -> AiContextData:
    with _lock:
        return _ai_context


def sync_backtest_summary_dict(summary: dict[str, Any] | None) -> None:
    global _backtest_summary
    with _lock:
        _backtest_summary = dict(summary) if summary else None


def get_backtest_summary_dict() -> dict[str, Any] | None:
    with _lock:
        return dict(_backtest_summary) if _backtest_summary else None


def set_backtest_summary(summary: BacktestSummary | None) -> None:
    sync_backtest_summary_dict(summary.to_dict() if summary else None)


def clear_all() -> None:
    global _ai_context, _backtest_summary, _market_quotes, _screening_result, _diagnose_result
    with _lock:
        _ai_context = AiContextData()
        _backtest_summary = None
        _market_quotes = []
        _screening_result = None
        _diagnose_result = None


def set_market_quotes_cache(items: list[Any], quotes: dict[str, Any]) -> None:
    global _market_quotes
    rows: list[dict[str, Any]] = []
    for item in items:
        tickflow_symbol = getattr(item, "tickflow_symbol", "")
        quote = quotes.get(tickflow_symbol)
        rows.append(
            {
                "symbol": getattr(item, "symbol", ""),
                "name": getattr(item, "name", ""),
                "vt_symbol": getattr(item, "vt_symbol", ""),
                "last_price": getattr(quote, "last_price", 0) if quote else 0,
                "change_pct": getattr(quote, "change_pct", 0) if quote else 0,
                "turnover_rate": getattr(quote, "turnover_rate", 0) if quote else 0,
                "volume": getattr(quote, "volume", 0) if quote else 0,
            }
        )
    with _lock:
        _market_quotes = rows


def get_market_quotes_cache() -> list[dict[str, Any]]:
    with _lock:
        return list(_market_quotes)


def set_screening_results(
    *,
    condition: str,
    rows: list[dict[str, Any]],
    updated_at: str | None = None,
) -> None:
    global _screening_result
    with _lock:
        _screening_result = ScreeningResultContext(
            condition=condition,
            count=len(rows),
            updated_at=updated_at,
            rows=list(rows),
        )


def get_screening_results() -> ScreeningResultContext | None:
    with _lock:
        if _screening_result is None:
            return None
        ctx = _screening_result
        return ScreeningResultContext(
            condition=ctx.condition,
            count=ctx.count,
            updated_at=ctx.updated_at,
            rows=list(ctx.rows),
        )


def set_diagnose_result(payload: dict[str, Any] | None) -> None:
    global _diagnose_result
    with _lock:
        _diagnose_result = dict(payload) if payload else None


def get_diagnose_result() -> dict[str, Any] | None:
    with _lock:
        return dict(_diagnose_result) if _diagnose_result else None
