"""隔日退出规则领域模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from vnpy_common.domain.base import FrozenModel

ExitSignal = Literal["buy", "sell", "hold", "na"]
RuleStatus = Literal["triggered", "near", "clear"]


class ExitRuleHit(FrozenModel):
    rule_id: str = Field(description="规则 ID")
    label: str = Field(description="展示标签")
    status: RuleStatus = Field(description="状态")
    detail: str = Field(description="详情说明")


class OvernightExitEvaluation(FrozenModel):
    signal: ExitSignal = Field(description="退出信号")
    ref_sell_price: float | None = Field(description="参考卖出价")
    rules: tuple[ExitRuleHit, ...] = Field(description="规则列表")
    warnings: tuple[str, ...] = Field(description="风险提示列表")
    reasons: tuple[str, ...] = Field(description="理由")

    def to_dict(self) -> dict[str, object]:
        signal_labels = {"sell": "卖出", "hold": "持有", "buy": "买入", "na": "不适用"}
        status_labels = {"triggered": "已触发", "near": "临近", "clear": "未触发"}
        return {
            "signal": self.signal,
            "signal_label": signal_labels.get(self.signal, self.signal),
            "ref_sell_price": self.ref_sell_price,
            "rules": [
                {
                    "rule_id": hit.rule_id,
                    "label": hit.label,
                    "status": hit.status,
                    "status_label": status_labels.get(hit.status, hit.status),
                    "detail": hit.detail,
                }
                for hit in self.rules
            ],
            "warnings": list(self.warnings),
            "reasons": list(self.reasons),
        }
