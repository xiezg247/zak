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
                description=("按总资金 2% 单笔风控规则计算建议最大股数。需用户在终端设置总资金；可传 cost_price、stop_loss_pct、volume 校验是否超限。"),
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
                description=("生成次日/指定日交易计划草案（情绪仓位 + 短线观察组 + 雷达共振），不自动写入；用户确认后由终端「今日计划」激活。"),
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
                name="get_trade_journal",
                description="查询结构化交易流水与违规汇总（off_plan、recession_buy 等）。",
                parameters={
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "起始日 YYYY-MM-DD"},
                        "end_date": {"type": "string", "description": "结束日 YYYY-MM-DD"},
                        "limit": {"type": "integer", "description": "条数上限，默认 50"},
                    },
                },
            ),
            ToolSpec(
                name="get_journal_report",
                description="近区间流水复盘报表：胜率、盈亏比、计划内/违规占比、已实现盈亏。",
                parameters={
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "起始日 YYYY-MM-DD"},
                        "end_date": {"type": "string", "description": "结束日 YYYY-MM-DD"},
                    },
                },
            ),
            ToolSpec(
                name="build_journal_prompt",
                description="生成盘后复盘 Prompt 文本（计划执行、流水统计、浮亏扛单、明细）。",
                parameters={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "统计天数，默认 1"},
                    },
                },
            ),
            ToolSpec(
                name="get_trading_discipline_context",
                description=("读取今日交易纪律快照：激活计划摘要、流水条数/违规、浮亏扛单、已实现盈亏与风控闸状态；可选 vt_symbol 校验计划内/违规标签。"),
                parameters={
                    "type": "object",
                    "properties": {
                        "trade_date": {"type": "string", "description": "YYYY-MM-DD，默认今日"},
                        "vt_symbol": {"type": "string", "description": "可选，校验是否在计划内"},
                    },
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
        from vnpy_ashare.trading.journal.propose import build_trading_plan_draft

        draft = build_trading_plan_draft(trade_date=trade_date)
        return json.dumps(draft, ensure_ascii=False)

    def get_trade_journal(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 50,
    ) -> str:
        from vnpy_ashare.storage.repositories.trade_journal import (
            query_trade_journal,
            summarize_trade_journal,
        )

        entries = query_trade_journal(
            start_date=start_date,
            end_date=end_date,
            limit=max(1, min(int(limit), 200)),
        )
        summary = summarize_trade_journal(start_date=start_date, end_date=end_date)
        return json.dumps(
            {
                "summary": summary,
                "entries": [
                    {
                        "id": item.id,
                        "vt_symbol": item.vt_symbol,
                        "side": item.side,
                        "trade_date": item.trade_date,
                        "price": item.price,
                        "volume": item.volume,
                        "on_plan": item.on_plan,
                        "violation_tags": list(item.violation_tags),
                        "pnl": item.pnl,
                        "emotion_stage": item.emotion_stage,
                        "reason": item.reason,
                    }
                    for item in entries
                ],
            },
            ensure_ascii=False,
        )

    def get_journal_report(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        from datetime import datetime, timedelta

        from vnpy_ashare.domain.time.market_hours import CHINA_TZ
        from vnpy_ashare.trading.journal.report import load_journal_report

        end = (end_date or "").strip() or datetime.now(CHINA_TZ).date().isoformat()
        if start_date:
            start = start_date.strip()
        else:
            end_day = datetime.strptime(end[:10], "%Y-%m-%d").date()
            start = (end_day - timedelta(days=6)).isoformat()
        report = load_journal_report(start_date=start, end_date=end)
        return json.dumps(report.to_dict(), ensure_ascii=False)

    def build_journal_prompt(self, days: int = 1) -> str:
        from vnpy_ashare.trading.journal.prompt import build_journal_prompt

        payload = build_journal_prompt(days=max(1, min(int(days), 30)))
        return json.dumps(payload, ensure_ascii=False)

    def get_trading_discipline_context(
        self,
        trade_date: str | None = None,
        vt_symbol: str | None = None,
    ) -> str:
        from vnpy_ashare.trading.journal.discipline_context import (
            build_trading_discipline_snapshot,
            format_trading_discipline_extra,
        )

        snapshot = build_trading_discipline_snapshot(trade_date=trade_date)
        payload: dict[str, object] = {"snapshot": snapshot}
        if vt_symbol:
            payload["formatted"] = format_trading_discipline_extra(
                vt_symbol=vt_symbol.strip(),
                trade_date=trade_date,
            )
        return json.dumps(payload, ensure_ascii=False)
