"""恐贪指数领域模型。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from vnpy_common.domain.base import MutableModel


class FearGreedComponent(MutableModel):
    """恐贪指数单个分项（score 0–100，越高越贪婪）。"""

    name: str = Field(description="名称")
    score: float = Field(description="得分")
    weight: float = Field(description="分项权重")
    raw: dict[str, Any] = Field(default_factory=dict, description="原始分项数据")
    hint: str = Field(default="", description="分项说明")


class FearGreedSnapshot(MutableModel):
    """某交易日恐贪指数快照。"""

    index: float = Field(description="恐贪指数（0–100）")
    label: str = Field(description="展示标签")
    trade_date: str = Field(description="交易日")
    as_of: str = Field(description="计算时间")
    components: list[FearGreedComponent] = Field(description="分项列表")
    warnings: list[str] = Field(default_factory=list, description="警告信息")
    sources: list[str] = Field(default_factory=list, description="数据来源列表")
    disclaimer: str = Field(default="恐贪指数由公开行情数据加权计算，仅供参考，不构成投资建议。", description="免责声明")

    def to_dict(self, *, include_components: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "index": round(self.index, 1),
            "label": self.label,
            "trade_date": self.trade_date,
            "as_of": self.as_of,
            "warnings": self.warnings,
            "sources": self.sources,
            "disclaimer": self.disclaimer,
        }
        if include_components:
            payload["components"] = [
                {
                    "name": item.name,
                    "score": round(item.score, 1),
                    "weight": item.weight,
                    "raw": item.raw,
                    "hint": item.hint,
                }
                for item in self.components
            ]
        return payload
