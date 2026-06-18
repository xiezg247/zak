"""系统提示词与页面 prompt。"""

from strategies.registry import STRATEGY_REGISTRY
from vnpy_common.ai.access import build_market_ai_prompt
from vnpy_llm.routing.base_prompt import BASE_PROMPT

# 无工具纯文本对话（stream_chat_completion）使用的轻量补充
GENERAL_CHAT_SUPPLEMENT = """【无工具模式】
当前未加载 Skill 工具。勿编造行情或选股结果。
可做 A 股投研概念解释；涉及实时数据、选股、诊断时请说明需启用工具与 API 配置。"""

SYSTEM_PROMPT = f"{BASE_PROMPT}\n\n{GENERAL_CHAT_SUPPLEMENT}"

BACKTEST_PAGE_PROMPT = """【策略回测页】
用户正在策略回测页。请协助解读回测指标（总收益、最大回撤、夏普、交易次数等）。
优先引用上下文中的「最近回测摘要」；需要历史对比时调用 list_backtest_history。
需要解读当前标的的策略规则状态时，可结合 list_strategy_signals 与 get_backtest_result。
不要编造回测数字或信号；若尚未回测，说明需用户先点击「开始回测」。"""

BATCH_BACKTEST_PAGE_PROMPT = """【批量回测对比页】
用户正在查看多标的同一策略的批量回测对比表。
请基于上下文中的批量统计（均值、最优/最差标的）做横向对比解读。
单只详情可建议用户跳转策略回测页。"""

SCREENING_PAGE_PROMPT = """【选股页】
用户正在查看选股结果。请优先 explain_screening_run 获取板块分布与 diff，再解读筛选列表。
需要历史某次运行时可传 run_id；对比前几只技术面时可设 batch_top_n（最多 10）。
不要编造未在结果中的标的或指标。
意图明确：形态用 screen_by_pattern，多因子用 run_recipe，内置 preset 用 screen_by_condition。
已保存方案、复杂自定义条件用 propose_screening / propose_recipe（解析后自动执行）。
禁止 run_python 执行选股（tdx-stock-picker 无 Python 模块）。"""

QUOTES_PAGE_PROMPT = """【看盘页】
用户正在看盘。问「当前这只」「我选中的」时优先 get_quote_context。
技术面问题可调用 technical_snapshot 或 get_bars_summary。
问「最近走势」「什么形态」时用 historical_pattern_summary（本地优先、MCP 兜底），仅描述历史统计。
问「走势预测」「5日情景」「方向倾向」「支撑压力」时优先 trend_scenario_summary，一次调用后通常即可作答。
问策略信号 / 双均线状态时调用 list_strategy_signals，不得给出具体买卖价位。"""

RADAR_PAGE_PROMPT = """【雷达页】
用户正在雷达页浏览盘面统计与共振侧栏。
问短线环境、情绪周期、能不能做、连板结构、龙头/主线时走 Market Agent 择时工具链。
可结合 get_emotion_cycle、check_risk_gate、run_leader_screen、get_short_term_watchlist。
「生成次日计划」场景用 propose_trading_plan（草案，须用户激活）。"""


def _market_page_prompt(page: str) -> str:
    """市场/雷达页注入 ashare 动态摘要（经 vnpy_common 桥接）。"""
    del page
    try:
        return build_market_ai_prompt(focus="intraday")
    except Exception:
        return ""


def build_page_prompt(page: str) -> str:
    if page == "策略回测":
        return BACKTEST_PAGE_PROMPT
    if page == "回测对比":
        return BATCH_BACKTEST_PAGE_PROMPT
    if page == "选股":
        return SCREENING_PAGE_PROMPT
    if page == "雷达":
        injected = _market_page_prompt(page)
        parts = [RADAR_PAGE_PROMPT]
        if injected:
            parts.append(injected)
        return "\n\n".join(parts)
    if page in ("自选", "市场", "本地"):
        if page == "市场":
            injected = _market_page_prompt(page)
            parts = [QUOTES_PAGE_PROMPT.replace("【看盘页】", "【市场页】")]
            if injected:
                parts.append(injected)
            return "\n\n".join(parts)
        return QUOTES_PAGE_PROMPT
    return ""


def build_strategy_prompt() -> str:
    """从策略注册表生成可注入 System Prompt 的策略摘要。"""
    if not STRATEGY_REGISTRY:
        return ""

    lines = ["【可用回测策略】"]
    for _name, meta in sorted(STRATEGY_REGISTRY.items()):
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
            params = "，".join(f"{n}={hint.split('，')[0]}" for n, hint in meta.param_hints)
            lines.append(f"  参数：{params}")
    return "\n".join(lines)
