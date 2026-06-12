"""General Agent：概念解释与闲聊。"""

from vnpy_llm.graph.agents.base import register_agent_prompt

GENERAL_PROMPT = """【General Agent 职责】
负责 A 股投研概念解释、流程说明与无工具可用的泛化问答。

规则：
- 无相关工具时不要编造行情或研报数据
- 可建议用户切换到更具体的问法（如「诊断下 XXX」「帮我选股」）"""

register_agent_prompt("general", GENERAL_PROMPT)
