"""选股筛选 Skill。"""

from __future__ import annotations

import json

from vnpy_skills.base import SkillTemplate, ToolSpec


class VnpyScreeningSkill(SkillTemplate):
    skill_name = "vnpy-screening"
    author = "zak"
    description = "按条件筛选标的（涨幅榜、换手率、成交量等）"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="list_screeners",
                description="列出所有可用的选股条件",
                parameters={"type": "object", "properties": {}},
            ),
            ToolSpec(
                name="screen_by_condition",
                description="按指定条件筛选标的，返回符合条件的前N只股票",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "选股条件：涨幅榜/换手率排行/成交量放大/自定义筛选/低 PE/中大盘/主力净流入",
                        },
                        "top_n": {
                            "type": "integer",
                            "description": "返回前 N 条，默认 10",
                        },
                    },
                    "required": ["name"],
                },
            ),
        ]

    def _load_quotes(self) -> list[dict] | str:
        from vnpy_ashare.ai.session_context import get_market_quotes_cache

        quotes = get_market_quotes_cache()
        if quotes:
            return quotes
        try:
            from vnpy_ashare.screener.quotes_loader import load_market_quote_rows

            snapshot = load_market_quote_rows()
            return snapshot.rows
        except Exception as ex:
            return json.dumps(
                {
                    "message": (
                        f"暂无可用的市场行情数据（{ex}）。"
                        "请运行「工具 → 立即执行 → 行情采集」，或使用「选股」页。"
                    ),
                },
                ensure_ascii=False,
            )

    def _get_screening_service(self):
        svc = self._services.get("screening")
        if svc is None:
            raise RuntimeError("ScreeningService 未就绪")
        return svc

    def list_screeners(self) -> str:
        svc = self._get_screening_service()
        names = svc.list_screeners()
        return json.dumps({"count": len(names), "screeners": names}, ensure_ascii=False)

    def run_screener(self, name: str, top_n: int = 10) -> str:
        from vnpy_ashare.screener.presets import get_preset
        from vnpy_ashare.screener.runner import ScreenerRequest, run_screener

        preset = get_preset(name)
        if preset is not None and preset.source == "tushare":
            try:
                result = run_screener(ScreenerRequest(preset=name, top_n=int(top_n or 10)))
                return self._format_results(name, result.rows)
            except Exception as ex:
                return json.dumps({"message": str(ex)}, ensure_ascii=False)

        quotes = self._load_quotes()
        if isinstance(quotes, str):
            return quotes

        svc = self._get_screening_service()
        results = svc.screen_by_condition(name, quotes, top_n=int(top_n or 10))
        if not results:
            return json.dumps(
                {
                    "message": f"选股条件「{name}」未匹配到标的，可用的条件见 list_screeners",
                    "count": 0,
                },
                ensure_ascii=False,
            )
        return self._format_results(name, results)

    def _format_results(self, name: str, results: list[dict]) -> str:
        summary = []
        for r in results:
            summary.append({
                "symbol": r.get("symbol", ""),
                "name": r.get("name", ""),
                "vt_symbol": r.get("vt_symbol", ""),
                "last_price": r.get("last_price"),
                "change_pct": r.get("change_pct"),
                "turnover_rate": r.get("turnover_rate"),
                "pe_ttm": r.get("pe_ttm"),
                "total_mv": r.get("total_mv"),
                "net_mf_amount": r.get("net_mf_amount"),
            })
        return json.dumps(
            {"condition": name, "count": len(summary), "results": summary},
            ensure_ascii=False,
        )

    def screen_by_condition(self, name: str, top_n: int = 10) -> str:
        return self.run_screener(name, top_n=top_n)
