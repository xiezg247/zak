"""回测生命周期管理 Service。"""

from __future__ import annotations

from typing import Any

from strategies.registry import (
    STRATEGY_REGISTRY,
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

    def get_last_summary(self) -> dict[str, Any] | None:
        """Skill 调用时获取最近一次回测摘要。"""
        if self._last_summary is None:
            return None
        return dict(self._last_summary)

    def clear_summary(self) -> None:
        self._last_summary = None
