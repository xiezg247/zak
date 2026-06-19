"""AI 工具名称 → 用户可读标签。"""

from __future__ import annotations

_TOOL_LABELS: dict[str, str] = {
    "get_quote_context": "读取当前上下文",
    "get_watchlist": "查询自选池",
    "get_short_term_watchlist": "查询信号区与共振",
    "get_bars_summary": "查询K线概览",
    "get_bars_data": "加载K线数据",
    "diagnose_stock": "综合诊断",
    "technical_snapshot": "分析技术形态",
    "list_strategy_signals": "查询策略信号",
    "list_watchlist_signal_panel": "扫描信号区",
    "historical_pattern_summary": "统计历史走势",
    "trend_scenario_summary": "走势情景摘要",
    "evaluate_entry_mode": "评估打板/半路/低吸",
    "assess_regulatory_deviation": "监管异动距离",
    "evaluate_overnight_exit": "隔日卖点检查",
    "check_risk_gate": "查询风控闸状态",
    "compute_position_size": "计算单笔建议股数",
    "propose_trading_plan": "生成交易计划草案",
    "get_trade_journal": "查询交易流水",
    "get_screening_context": "读取选股结果",
    "explain_screening_run": "编排选股解读",
    "list_strategies": "列出可用策略",
    "get_backtest_result": "读取回测结果",
    "list_backtest_history": "查询回测历史",
    "list_screeners": "列出选股条件",
    "list_recipes": "列出多因子配方",
    "run_recipe": "执行多因子选股",
    "propose_screening": "解析选股（需确认）",
    "propose_recipe": "解析多因子（需确认）",
    "screen_by_condition": "执行选股筛选",
    "screen_by_pattern": "执行形态选股",
    "screen_reference_peer": "标杆同业选股",
    "list_watchlist_positions": "查询自选持仓",
    "add_to_watchlist": "加入自选",
    "remove_from_watchlist": "移出自选",
    "get_stock_notes": "查询个股笔记",
    "append_stock_note_entry": "追加笔记流水",
    "update_stock_note_memo": "更新备忘",
    "delete_stock_note_entry": "删除笔记流水",
    "clear_stock_notes": "清空个股笔记",
    "list_stock_analysis_reports": "列出分析报告",
    "get_stock_analysis_report": "读取分析报告全文",
    "read_skill_file": "读取知识文档",
    "run_python": "执行数据分析",
    "list_skill_files": "列出 Skill 文件",
    "get_ashare_fear_greed_index": "查询 A 股恐贪指数",
    "get_emotion_cycle": "查询 A 股情绪周期",
}


def tool_display_name(name: str) -> str:
    if name in _TOOL_LABELS:
        return _TOOL_LABELS[name]
    if name.startswith("mcp_tdx_"):
        suffix = name.removeprefix("mcp_tdx_")
        if "f10" in suffix or "fundamental" in suffix:
            return "查询通达信基本面"
        if "quote" in suffix or "price" in suffix:
            return "查询通达信行情"
        if "kline" in suffix or "bar" in suffix:
            return "查询通达信 K 线"
        return f"通达信 MCP ({suffix})"
    return name
