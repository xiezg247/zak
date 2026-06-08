"""系统提示词。"""

SYSTEM_PROMPT = """你是 zak A 股量化终端的投研助手。

规则：
1. 只讨论 A 股投资研究，不提供具体买卖建议或操作指令
2. 涉及价格、涨跌、持仓等信息时，必须基于工具返回的真实数据，禁止编造行情数据
3. 若 K 线查询结果显示无本地数据，提示用户先在看盘页下载日K，不要假设已有数据
4. 回答简洁清晰，适当使用条目列表
5. 价格与涨跌幅保留 2 位小数

免责声明：AI 生成内容仅供参考，不构成投资建议。"""

BACKTEST_PAGE_PROMPT = """【策略回测页】
用户正在策略回测页。请协助解读回测指标（总收益、最大回撤、夏普、交易次数等）。
优先引用上下文中的「最近回测摘要」；需要历史对比时调用 list_backtest_history。
不要编造回测数字；若尚未回测，说明需用户先点击「开始回测」。"""

BATCH_BACKTEST_PAGE_PROMPT = """【批量回测对比页】
用户正在查看多标的同一策略的批量回测对比表。
请基于上下文中的批量统计（均值、最优/最差标的）做横向对比解读。
单只详情可建议用户跳转策略回测页。"""


def build_page_prompt(page: str) -> str:
    if page == "策略回测":
        return BACKTEST_PAGE_PROMPT
    if page == "回测对比":
        return BATCH_BACKTEST_PAGE_PROMPT
    return ""


def build_strategy_prompt() -> str:
    """从策略注册表生成可注入 System Prompt 的策略摘要。"""
    from strategies.registry import STRATEGY_REGISTRY

    if not STRATEGY_REGISTRY:
        return ""

    lines = ["【可用回测策略】"]
    for name, meta in sorted(STRATEGY_REGISTRY.items()):
        tags = " · ".join(meta.tags)
        lines.append(f"- {meta.title}（{tags}）")
        lines.append(f"  说明：{meta.summary}")
        if meta.scenarios:
            scenarios = "；".join(meta.scenarios)
            lines.append(f"  适用：{scenarios}")
        if meta.anti_scenarios:
            anti = "；".join(meta.anti_scenarios)
            lines.append(f"  不适用：{anti}")
        if meta.param_hints:
            params = "，".join(
                f"{n}={hint.split('，')[0]}" for n, hint in meta.param_hints
            )
            lines.append(f"  参数：{params}")
    return "\n".join(lines)
