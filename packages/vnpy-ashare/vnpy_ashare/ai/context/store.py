"""AI 会话内存存储（线程安全）；业务代码请经 Service 访问。

写入方（唯一）::

    QuoteService.publish_quote_context / set_current_selection
    AnalysisService.set_diagnose_result
    ScreeningService.persist_run_result → publish_screener_page_context
    BarService.publish_data_manager_context
    backtest_context.sync_*（经 BacktestService 或模块函数）

读取方::

    vnpy_llm Skill / ai/ui（只读 get_*）
    context_store.register_context_listener（AI 面板刷新）

UI 层禁止 ``from vnpy_ashare.ai.context.store import set_*``。
"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.domain.base import MutableModel

import threading
from collections.abc import Callable
from typing import Any

from vnpy_ashare.quotes.core.quote_rows import (
    clear_market_quote_rows_cache,
)
from vnpy_common.ai.protocol import AiContextData

_lock = threading.Lock()
_listeners: list[Callable[[AiContextData], None]] = []
_ai_context = AiContextData()
_backtest_summary: dict[str, Any] | None = None
_market_overview_context: dict[str, Any] | None = None


class BacktestSummary(MutableModel):
    """最近一次回测摘要。"""

    strategy: str = Field(description="strategy")
    vt_symbol: str = Field(description="VeighNa 合约代码")
    interval: str = Field(description="interval")
    start: str = Field(description="开始日期")
    end: str = Field(description="结束日期")
    statistics: dict[str, Any] = Field(default_factory=dict, description="statistics")

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "vt_symbol": self.vt_symbol,
            "interval": self.interval,
            "start": self.start,
            "end": self.end,
            "statistics": self.statistics,
        }


class ScreeningResultContext(MutableModel):
    """最近一次选股结果快照（供 Skill / 悬浮球读取）。"""

    condition: str = Field(description="condition")
    count: int = Field(description="数量")
    updated_at: str | None = Field(description="更新时间")
    rows: list[dict[str, Any]] = Field(description="数据行列表")


_screening_result: ScreeningResultContext | None = None
_diagnose_result: dict[str, Any] | None = None


def register_context_listener(callback: Callable[[AiContextData], None]) -> None:
    """注册 AI 上下文变更监听（如悬浮球刷新 chip / actions）。"""
    with _lock:
        if callback not in _listeners:
            _listeners.append(callback)


def set_ai_context(data: AiContextData) -> None:
    """写入当前页 AI 上下文；变更后异步通知已注册 listener。"""
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
    """读取当前页 AI 上下文（Skill / 悬浮球只读）。"""
    with _lock:
        return _ai_context


def sync_backtest_summary_dict(summary: dict[str, Any] | None) -> None:
    """写入回测摘要 dict（BacktestService / backtest_context 调用）。"""
    global _backtest_summary
    with _lock:
        _backtest_summary = dict(summary) if summary else None


def get_backtest_summary_dict() -> dict[str, Any] | None:
    """读取最近一次回测摘要 dict。"""
    with _lock:
        return dict(_backtest_summary) if _backtest_summary else None


def set_backtest_summary(summary: BacktestSummary | None) -> None:
    """写入回测摘要（``BacktestSummary`` 转 dict 后存 session）。"""
    sync_backtest_summary_dict(summary.to_dict() if summary else None)


def clear_all() -> None:
    """清空全部 session 缓存（登出 / 重置时）。"""
    global _ai_context, _backtest_summary, _market_overview_context, _screening_result, _diagnose_result
    with _lock:
        _ai_context = AiContextData()
        _backtest_summary = None
        _market_overview_context = None
        _screening_result = None
        _diagnose_result = None
    clear_market_quote_rows_cache()


def set_market_overview_context(payload: dict[str, Any] | None) -> None:
    """写入市场页大盘概览摘要（MarketOverviewController 经 sync 调用）。"""
    global _market_overview_context
    with _lock:
        _market_overview_context = dict(payload) if payload else None


def get_market_overview_context() -> dict[str, Any] | None:
    with _lock:
        if _market_overview_context is None:
            return None
        return dict(_market_overview_context)


def set_screening_results(
    *,
    condition: str,
    rows: list[dict[str, Any]],
    updated_at: str | None = None,
) -> None:
    """写入选股结果快照（ScreeningService.persist_run_result 调用）。"""
    global _screening_result
    with _lock:
        _screening_result = ScreeningResultContext(
            condition=condition,
            count=len(rows),
            updated_at=updated_at,
            rows=list(rows),
        )


def get_screening_results() -> ScreeningResultContext | None:
    """读取选股结果快照（返回副本，避免外部修改）。"""
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
    """写入综合诊断结果（AnalysisService 调用）。"""
    global _diagnose_result
    with _lock:
        _diagnose_result = dict(payload) if payload else None


def get_diagnose_result() -> dict[str, Any] | None:
    """读取综合诊断结果。"""
    with _lock:
        return dict(_diagnose_result) if _diagnose_result else None
