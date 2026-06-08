"""自选池管理 Skill。"""

from __future__ import annotations

import json

from vnpy_ashare.ai.symbol import parse_stock_symbol
from vnpy_skills.base import SkillTemplate, ToolSpec

WATCHLIST_LIMIT = 80


class VnpyWatchlistSkill(SkillTemplate):
    skill_name = "vnpy-watchlist"
    author = "vnpy_zak"
    description = "查看自选池、管理自选标的"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="get_watchlist",
                description="获取自选池列表（代码、名称、交易所）",
                parameters={"type": "object", "properties": {}},
            ),
            ToolSpec(
                name="add_to_watchlist",
                description="添加标的到自选池",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码，如 600519.SSE",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            ToolSpec(
                name="remove_from_watchlist",
                description="从自选池移除标的",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码，如 600519.SSE",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
        ]

    def _get_watchlist_service(self):
        svc = self._services.get("watchlist")
        if svc is None:
            raise RuntimeError("WatchlistService 未就绪")
        return svc

    def get_watchlist(self) -> str:
        svc = self._get_watchlist_service()
        items = svc.get_items()
        total = len(items)
        rows = items[:WATCHLIST_LIMIT]
        payload: dict = {"total": total, "items": rows}
        if total > WATCHLIST_LIMIT:
            payload["truncated"] = True
            payload["message"] = f"仅返回前 {WATCHLIST_LIMIT} 条，共 {total} 只"
        return json.dumps(payload, ensure_ascii=False)

    def add_to_watchlist(self, symbol: str) -> str:
        item = parse_stock_symbol(symbol)
        if item is None:
            return json.dumps(
                {"error": f"无法解析代码: {symbol}，请使用 600519.SSE 格式"},
                ensure_ascii=False,
            )
        svc = self._get_watchlist_service()
        ok = svc.add(item.symbol, item.exchange)
        return json.dumps(
            {
                "success": ok,
                "symbol": item.vt_symbol,
                "message": (
                    f"{item.vt_symbol} 已加入自选"
                    if ok
                    else f"{item.vt_symbol} 已在自选池中"
                ),
            },
            ensure_ascii=False,
        )

    def remove_from_watchlist(self, symbol: str) -> str:
        item = parse_stock_symbol(symbol)
        if item is None:
            return json.dumps(
                {"error": f"无法解析代码: {symbol}，请使用 600519.SSE 格式"},
                ensure_ascii=False,
            )
        svc = self._get_watchlist_service()
        ok = svc.remove(item.symbol, item.exchange)
        return json.dumps(
            {
                "success": ok,
                "symbol": item.vt_symbol,
                "message": (
                    f"{item.vt_symbol} 已移出自选"
                    if ok
                    else f"{item.vt_symbol} 不在自选池中"
                ),
            },
            ensure_ascii=False,
        )
