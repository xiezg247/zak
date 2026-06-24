"""数据查询 Skill：K 线、行情。"""

from __future__ import annotations

import json

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_skills.domain.template import SkillTemplate, ToolSpec


class VnpyDataSkill(SkillTemplate):
    skill_name = "vnpy-data"
    author = "zak"
    description = "查询本地 K 线概览、历史数据、区间涨跌"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="get_bars_summary",
                description="查询本地 K 线的条数、日期区间以及近 N 日区间涨跌（无 OHLCV，聊天不出 K 线图；需可视化时用 get_bars_data 或 technical_snapshot）",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码，如 600519.SSE",
                        },
                        "scope": {
                            "type": "string",
                            "description": "K 线范围：daily（日K，默认）或 1m（1分钟）",
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
                name="get_bars_data",
                description="获取指定标的最近 N 根 K 线的 OHLCV；终端会在聊天中自动展示 K 线迷你图。技术面综述优先用 technical_snapshot",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码，如 600519.SSE",
                        },
                        "scope": {
                            "type": "string",
                            "description": "K 线范围：daily（日K，默认）或 1m（1分钟）",
                        },
                        "days": {
                            "type": "integer",
                            "description": "返回最近多少天/根的数据，默认 30，最大 100",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
        ]

    def _get_bar_service(self):
        svc = self._services.get("bar")
        if svc is None:
            raise RuntimeError("BarService 未就绪")
        return svc

    def get_bars_summary(
        self,
        symbol: str,
        scope: str = "daily",
        lookback_days: int = 20,
    ) -> str:
        item = parse_stock_symbol(symbol)
        if item is None:
            return json.dumps({"error": f"无法解析代码: {symbol}"}, ensure_ascii=False)

        bar_svc = self._get_bar_service()
        overview = bar_svc.get_overview(item.symbol, item.exchange, scope or "daily")

        if overview is None:
            return json.dumps(
                {
                    "symbol": item.vt_symbol,
                    "scope": scope or "daily",
                    "count": 0,
                    "message": "本地暂无该周期 K 线，请先在数据管理页下载",
                },
                ensure_ascii=False,
            )

        payload: dict = {
            "symbol": item.vt_symbol,
            "scope": overview.period,
            "count": overview.count,
            "start": overview.start.strftime("%Y-%m-%d"),
            "end": overview.end.strftime("%Y-%m-%d"),
        }

        return_info = bar_svc.get_return(
            item.symbol,
            item.exchange,
            scope or "daily",
            lookback_days=max(2, min(int(lookback_days or 20), 250)),
        )
        if "return_pct" in return_info:
            payload.update({k: v for k, v in return_info.items() if k != "symbol"})

        return json.dumps(payload, ensure_ascii=False)

    def get_bars_data(
        self,
        symbol: str,
        scope: str = "daily",
        days: int = 30,
    ) -> str:
        item = parse_stock_symbol(symbol)
        if item is None:
            return json.dumps({"error": f"无法解析代码: {symbol}"}, ensure_ascii=False)

        bar_svc = self._get_bar_service()
        n = max(1, min(int(days or 30), 100))
        bars = bar_svc.load_bars(item.symbol, item.exchange, scope or "daily")
        tail = bars[-n:] if len(bars) >= n else bars

        rows = []
        for bar in tail:
            rows.append(
                {
                    "date": bar.datetime.strftime("%Y-%m-%d"),
                    "open": round(bar.open_price, 2),
                    "high": round(bar.high_price, 2),
                    "low": round(bar.low_price, 2),
                    "close": round(bar.close_price, 2),
                    "volume": int(bar.volume),
                }
            )

        return json.dumps(
            {
                "symbol": item.vt_symbol,
                "scope": scope or "daily",
                "count": len(rows),
                "data": rows,
            },
            ensure_ascii=False,
        )
