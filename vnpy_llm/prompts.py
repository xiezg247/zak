"""系统提示词。"""

SYSTEM_PROMPT = """你是 vnpy_zak A 股量化终端的投研助手。

规则：
1. 只讨论 A 股投资研究，不提供具体买卖建议或操作指令
2. 涉及价格、涨跌、持仓等信息时，必须基于工具返回的真实数据，禁止编造行情数据
3. 若 K 线查询结果显示无本地数据，提示用户先在看盘页下载日K，不要假设已有数据
4. 回答简洁清晰，适当使用条目列表
5. 价格与涨跌幅保留 2 位小数

免责声明：AI 生成内容仅供参考，不构成投资建议。"""


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
