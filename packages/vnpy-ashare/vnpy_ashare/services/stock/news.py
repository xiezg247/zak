"""个股新闻查询（供 AI Skill 与 Service 调用）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.integrations.events.news import NewsFetchError, fetch_stock_news


def get_stock_news_for_symbol(symbol: str, *, limit: int = 20) -> dict[str, Any]:
    """按 vt_symbol / ts_code 拉取近期新闻。"""
    item = parse_stock_symbol(symbol)
    if item is None:
        return {
            "ok": False,
            "symbol": symbol,
            "message": "无法解析股票代码",
            "news": [],
            "count": 0,
        }

    try:
        rows = fetch_stock_news(item.ts_code, limit=max(1, min(int(limit or 20), 50)))
    except NewsFetchError as ex:
        return {
            "ok": False,
            "symbol": item.vt_symbol,
            "ts_code": item.ts_code,
            "message": str(ex),
            "news": [],
            "count": 0,
        }

    return {
        "ok": True,
        "symbol": item.vt_symbol,
        "ts_code": item.ts_code,
        "news": rows,
        "count": len(rows),
        "disclaimer": "新闻为媒体报道摘要，不构成投资建议；重大事项以法定公告为准。",
    }
