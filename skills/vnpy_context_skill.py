"""vnpy_zak 终端上下文 Skill：自选、本地 K 线、回测摘要。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from vnpy_ashare.ai.session_context import get_ai_context, get_backtest_summary
from vnpy_ashare.ai.symbol import parse_stock_symbol
from vnpy_ashare.bar_store import get_period_overview, load_scope_bars
from vnpy_ashare.bars import load_watchlist
from vnpy_skills.base import SkillTemplate, ToolSpec

WATCHLIST_LIMIT = 80
LOOKBACK_MAX = 250


class VnpyContextSkill(SkillTemplate):
    skill_name = "vnpy-context"
    author = "vnpy_zak"
    description = "读取 vnpy_zak 终端自选池、本地 K 线、当前选中标的与最近回测结果"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="get_quote_context",
                description=(
                    "获取终端当前页面与选中标的上下文（页面名、代码、行情摘要、本地 K 线条数）。"
                    "用户问「当前这只」「我选中的」时优先调用。"
                ),
                parameters={"type": "object", "properties": {}},
            ),
            ToolSpec(
                name="get_watchlist",
                description="获取本地自选池列表（代码、名称、交易所）",
                parameters={"type": "object", "properties": {}},
            ),
            ToolSpec(
                name="get_bars_summary",
                description=(
                    "查询本地已下载 K 线的条数、日期区间，以及近 N 个交易日的区间涨跌"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码，如 600519.SSE 或 600519.SH",
                        },
                        "scope": {
                            "type": "string",
                            "description": "K 线范围：daily（日 K，默认）或 1m（1 分钟）",
                        },
                        "lookback_days": {
                            "type": "integer",
                            "description": "计算区间涨跌使用的最近交易日数，默认 20",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            ToolSpec(
                name="get_backtest_summary",
                description="获取最近一次策略回测的摘要指标（收益、回撤、夏普等）",
                parameters={"type": "object", "properties": {}},
            ),
        ]

    def get_quote_context(self) -> str:
        ctx = get_ai_context()
        payload = {
            "page": ctx.page,
            "symbol": ctx.symbol,
            "exchange": ctx.exchange,
            "name": ctx.name,
            "quote_summary": ctx.quote_summary,
            "extra": ctx.extra,
            "text": ctx.to_text(),
        }
        if not ctx.symbol and not ctx.page:
            payload["message"] = "终端尚未推送选中标的，请用户在看盘页选中股票后再问"
        return json.dumps(payload, ensure_ascii=False)

    def get_watchlist(self) -> str:
        items = load_watchlist()
        total = len(items)
        rows = [
            {
                "symbol": item.symbol,
                "exchange": item.exchange.value,
                "name": item.name,
                "vt_symbol": item.vt_symbol,
            }
            for item in items[:WATCHLIST_LIMIT]
        ]
        payload: dict = {"total": total, "items": rows}
        if total > WATCHLIST_LIMIT:
            payload["truncated"] = True
            payload["message"] = f"仅返回前 {WATCHLIST_LIMIT} 条，共 {total} 只"
        return json.dumps(payload, ensure_ascii=False)

    def get_bars_summary(
        self,
        symbol: str,
        scope: str = "daily",
        lookback_days: int = 20,
    ) -> str:
        item = parse_stock_symbol(symbol)
        if item is None:
            return json.dumps({"error": f"无法解析代码: {symbol}"}, ensure_ascii=False)

        normalized_scope = scope.strip().lower() or "daily"
        overview = get_period_overview(item.symbol, item.exchange, normalized_scope)
        if overview is None:
            return json.dumps(
                {
                    "symbol": item.vt_symbol,
                    "scope": normalized_scope,
                    "count": 0,
                    "message": "本地暂无该周期 K 线，请先在数据管理页下载",
                },
                ensure_ascii=False,
            )

        payload: dict = {
            "symbol": item.vt_symbol,
            "scope": normalized_scope,
            "count": overview.count,
            "start": overview.start.strftime("%Y-%m-%d"),
            "end": overview.end.strftime("%Y-%m-%d"),
        }

        days = max(2, min(int(lookback_days or 20), LOOKBACK_MAX))
        if normalized_scope == "daily" and overview.count >= 2:
            end_dt = overview.end
            start_dt = end_dt - timedelta(days=days * 2)
            bars = load_scope_bars(
                item.symbol,
                item.exchange,
                normalized_scope,
                start_dt,
                end_dt,
            )
            if len(bars) >= 2:
                tail = bars[-days:] if len(bars) >= days else bars
                first_close = tail[0].close_price
                last_close = tail[-1].close_price
                if first_close:
                    payload["lookback_days"] = len(tail)
                    payload["lookback_start"] = tail[0].datetime.strftime("%Y-%m-%d")
                    payload["lookback_end"] = tail[-1].datetime.strftime("%Y-%m-%d")
                    payload["lookback_return_pct"] = round(
                        (last_close - first_close) / first_close * 100,
                        2,
                    )
                    payload["lookback_close_start"] = round(first_close, 2)
                    payload["lookback_close_end"] = round(last_close, 2)

        return json.dumps(payload, ensure_ascii=False)

    def get_backtest_summary(self) -> str:
        summary = get_backtest_summary()
        if summary is None:
            return json.dumps(
                {
                    "message": "暂无回测摘要，请先在策略回测页完成一次回测",
                },
                ensure_ascii=False,
            )
        return json.dumps(summary, ensure_ascii=False)
