"""注册各 Specialist Agent 的 prompt 切片。"""

from vnpy_llm.graph.agents import backtest, chief, data, financial, general, market, research, risk, screening, strategy
from vnpy_llm.graph.agents.base import build_agent_system_prompt, get_agent_domain_prompt

__all__ = [
    "backtest",
    "build_agent_system_prompt",
    "chief",
    "data",
    "financial",
    "general",
    "get_agent_domain_prompt",
    "market",
    "research",
    "risk",
    "screening",
    "strategy",
]
