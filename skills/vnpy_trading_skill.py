"""交易风控 Skill。"""

from __future__ import annotations

import json

from vnpy_skills.domain import SkillTemplate, ToolSpec


class VnpyTradingSkill(SkillTemplate):
    skill_name = "vnpy-trading"
    author = "zak"
    description = "账户风控闸与情绪周期合并状态，供 AI 判断是否建议新开仓"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="check_risk_gate",
                description=(
                    "查询账户风控闸（normal/caution/halt）与情绪周期合并结果，"
                    "含 allow_new_positions、当日盈亏、情绪建议仓位区间。"
                    "适合：还能不能开仓、账户是否熔断、环境与账户双重约束。"
                    "halt/caution 或退潮/冰点时须引用返回的具体数字与 warnings，禁止编造。"
                ),
                parameters={"type": "object", "properties": {}},
            ),
            ToolSpec(
                name="compute_position_size",
                description=(
                    "按总资金 2% 单笔风控规则计算建议最大股数。"
                    "需用户在终端设置总资金；可传 cost_price、stop_loss_pct、volume 校验是否超限。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "cost_price": {
                            "type": "number",
                            "description": "成本价，必填",
                        },
                        "stop_loss_pct": {
                            "type": "number",
                            "description": "止损比例（小数，如 0.05 表示 5%），默认读用户设置",
                        },
                        "volume": {
                            "type": "integer",
                            "description": "计划股数，可选，用于判断是否超出建议",
                        },
                    },
                    "required": ["cost_price"],
                },
            ),
        ]

    def check_risk_gate(self) -> str:
        from vnpy_ashare.trading.risk.combined import load_combined_risk_gate_snapshot

        snapshot = load_combined_risk_gate_snapshot()
        return json.dumps(snapshot.to_dict(), ensure_ascii=False)

    def compute_position_size(
        self,
        cost_price: float,
        stop_loss_pct: float | None = None,
        volume: int | None = None,
    ) -> str:
        from vnpy_ashare.config.preferences.trading_risk import load_trading_risk_prefs
        from vnpy_ashare.trading.risk.position_size import compute_position_size_from_prefs

        prefs = load_trading_risk_prefs()
        if prefs.total_capital is None:
            return json.dumps(
                {"error": "未设置总资金，请在自选页持仓区「风控设置」填写"},
                ensure_ascii=False,
            )
        result = compute_position_size_from_prefs(
            cost_price=float(cost_price),
            requested_volume=int(volume) if volume is not None else None,
            stop_loss_pct=float(stop_loss_pct) if stop_loss_pct is not None else None,
        )
        if result is None:
            return json.dumps({"error": "参数无效，请检查成本价与止损比例"}, ensure_ascii=False)
        return json.dumps(result.to_dict(), ensure_ascii=False)
