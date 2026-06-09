"""回测生命周期管理 Service。"""

from __future__ import annotations

from typing import Any

from strategies.registry import (
    STRATEGY_REGISTRY,
)
from vnpy_ashare.backtest.run_store import (
    get_latest_backtest_run,
    list_backtest_runs,
    save_backtest_summary_dict,
)
from vnpy_ashare.services.base import BaseService


class BacktestService(BaseService):
    """触发回测、管理结果摘要。"""

    def __init__(self, engine: "AshareEngine") -> None:  # type: ignore[name-defined]
        super().__init__(engine)
        self._last_summary: dict[str, Any] | None = None

    def list_strategies(self) -> list[dict[str, Any]]:
        """返回可用 A 股策略元数据。"""
        result: list[dict[str, Any]] = []
        for name, meta in sorted(STRATEGY_REGISTRY.items()):
            result.append({
                "class_name": meta.class_name,
                "title": meta.title,
                "summary": meta.summary,
                "tags": list(meta.tags),
                "scenarios": list(meta.scenarios),
                "anti_scenarios": list(meta.anti_scenarios),
            })
        return result

    def set_last_summary(self, summary: dict[str, Any] | None) -> None:
        """由 BacktesterWidget 回测完成后调用。"""
        self._last_summary = dict(summary) if summary else None

    def persist_summary(self, summary: dict[str, Any], *, source: str = "single") -> None:
        """写入内存、落库，并同步 session_context 供回测页 AI 读取。"""
        payload = dict(summary)
        self.set_last_summary(payload)
        save_backtest_summary_dict(payload, source=source)
        from vnpy_ashare.ai.session_context import sync_backtest_summary_dict

        sync_backtest_summary_dict(payload)

    def get_last_summary(self) -> dict[str, Any] | None:
        """Skill 与 UI 获取最近一次回测摘要。"""
        if self._last_summary is not None:
            return dict(self._last_summary)
        latest = get_latest_backtest_run()
        if latest is None:
            return None
        summary = latest.to_summary_dict()
        self._last_summary = summary
        from vnpy_ashare.ai.session_context import sync_backtest_summary_dict

        sync_backtest_summary_dict(summary)
        return dict(summary)

    def list_recent_summaries(self, *, limit: int = 10) -> list[dict[str, Any]]:
        return [record.to_summary_dict() for record in list_backtest_runs(limit=limit)]

    def clear_summary(self) -> None:
        self._last_summary = None
