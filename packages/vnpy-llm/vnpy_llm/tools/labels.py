"""AI 工具名称 → 用户可读标签。"""

from __future__ import annotations

_TOOL_LABELS: dict[str, str] = {
    "get_quote_context": "读取当前上下文",
    "get_watchlist": "查询自选池",
    "get_bars_summary": "查询K线概览",
    "get_bars_data": "加载K线数据",
    "diagnose_stock": "综合诊断",
    "technical_snapshot": "分析技术形态",
    "list_strategy_signals": "查询策略信号",
    "historical_pattern_summary": "统计历史走势",
    "get_screening_context": "读取选股结果",
    "explain_screening_run": "编排选股解读",
    "list_strategies": "列出可用策略",
    "get_backtest_result": "读取回测结果",
    "list_backtest_history": "查询回测历史",
    "list_screeners": "列出选股条件",
    "propose_screening": "解析选股条件",
    "screen_by_condition": "执行选股筛选",
    "screen_by_pattern": "执行形态选股",
    "add_to_watchlist": "加入自选",
    "remove_from_watchlist": "移出自选",
    "read_skill_file": "读取知识文档",
    "run_python": "执行数据分析",
    "list_skill_files": "列出 Skill 文件",
    "get_ashare_fear_greed_index": "查询 A 股恐贪指数",
}


def tool_display_name(name: str) -> str:
    if name in _TOOL_LABELS:
        return _TOOL_LABELS[name]
    if name.startswith("mcp_tdx_"):
        suffix = name.removeprefix("mcp_tdx_")
        if any(key in suffix for key in ("report", "research", "yanbao", "rating")):
            return "查询通达信研报"
        if "f10" in suffix:
            return "查询通达信 F10"
        if "quote" in suffix or "price" in suffix:
            return "查询通达信行情"
        if "kline" in suffix or "bar" in suffix:
            return "查询通达信 K 线"
        return f"通达信 MCP ({suffix})"
    return name
