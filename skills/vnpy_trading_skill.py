"""交易计划与持仓策略 Skill。"""

from __future__ import annotations

import json

from vnpy_skills.domain.template import SkillTemplate, ToolSpec


class VnpyTradingSkill(SkillTemplate):
    skill_name = "vnpy-trading"
    author = "zak"
    description = "交易计划与隔日退出规则，供 AI 结合情绪周期做择时参考"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="get_trading_plan",
                description="读取指定交易日的激活交易计划（观察名单、计划总仓位、预期情绪）。",
                parameters={
                    "type": "object",
                    "properties": {
                        "trade_date": {
                            "type": "string",
                            "description": "YYYY-MM-DD，默认今日",
                        },
                    },
                },
            ),
            ToolSpec(
                name="propose_trading_plan",
                description=("生成次日/指定日交易计划草案（情绪仓位 + 信号区 + 雷达共振），不自动写入；用户确认后由终端「今日计划」激活。"),
                parameters={
                    "type": "object",
                    "properties": {
                        "trade_date": {
                            "type": "string",
                            "description": "计划适用日 YYYY-MM-DD，默认次日",
                        },
                    },
                },
            ),
            ToolSpec(
                name="evaluate_overnight_exit",
                description=(
                    "评估极致短线隔日退出规则（止损、开盘 30 分钟止损、低开走弱、炸板、冲高量能不足等）。"
                    "须标的已在自选页持仓区；不传 symbol 时扫描全部持仓。"
                    "返回 signal（sell/hold）、规则触发状态与参考卖价；T+1 锁定日 signal 为 hold。"
                    "须引用返回的 rules/warnings，禁止编造价位。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码或 vt_symbol，如 600519 或 600519.SSE；省略则扫描全部持仓",
                        },
                    },
                },
            ),
        ]

    def get_trading_plan(self, trade_date: str | None = None) -> str:
        from datetime import datetime

        from vnpy_ashare.domain.time.market_hours import CHINA_TZ
        from vnpy_ashare.storage.repositories.trading_plans import load_active_trading_plan

        day = (trade_date or "").strip() or datetime.now(CHINA_TZ).date().isoformat()
        plan = load_active_trading_plan(day)
        if plan is None:
            return json.dumps({"trade_date": day, "active": False}, ensure_ascii=False)
        return json.dumps(
            {
                "trade_date": day,
                "active": True,
                "id": plan.id,
                "emotion_expected": plan.emotion_expected,
                "max_position_pct": plan.max_position_pct,
                "notes": plan.notes,
                "watchlist": list(plan.watchlist_vt_symbols),
                "status": plan.status,
            },
            ensure_ascii=False,
        )

    def propose_trading_plan(self, trade_date: str | None = None) -> str:
        from vnpy_ashare.trading.plan.propose import build_trading_plan_draft

        draft = build_trading_plan_draft(trade_date=trade_date)
        return json.dumps(draft, ensure_ascii=False)

    def evaluate_overnight_exit(self, symbol: str | None = None) -> str:
        from vnpy_ashare.trading.exit.for_symbol import (
            evaluate_all_overnight_exits,
            evaluate_overnight_exit_for_symbol,
        )

        text = (symbol or "").strip()
        if not text:
            payload = evaluate_all_overnight_exits()
        else:
            payload = evaluate_overnight_exit_for_symbol(text)
        return json.dumps(payload, ensure_ascii=False)
