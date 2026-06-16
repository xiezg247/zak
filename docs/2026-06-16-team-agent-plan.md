# 智能体投研团队实施计划

> **For agentic workers:** 按顺序执行每个 Task，步间提交。每个 Task 包含精确路径与完整代码。

**Goal:** 实现财务、风险、策略三 Agent 并行分析 + chief 汇总的团队协作模式

**Architecture:** 在现有串行路由基础上新增并行扇出路径——Orchestrator 用 ThreadPoolExecutor 调度 3 个子 Agent 独立 ReAct，产出结构化 JSON 后由 chief 汇总

**Tech Stack:** Python 3.10+, LangGraph, concurrent.futures, Pydantic, 复用现有 Agent 注册/工具过滤/Skill 引擎

---

### Task 1: 扩展 IntentCategory 与路由分类

**Files:**
- Modify: `packages/vnpy-llm/vnpy_llm/routing/intent.py:9-18`
- Modify: `packages/vnpy-llm/vnpy_llm/routing/router.py`（三处：分类 prompt + TOOL_GROUPS + 关键词兜底 + /team 命令）

- [ ] **Step 1: 扩展 IntentCategory**

在 `intent.py` 第 9 行后追加 `"team_analysis"`：

```python
IntentCategory = Literal[
    "general",
    "quote",
    "technical",
    "diagnosis",
    "screening",
    "backtest",
    "watchlist",
    "data",
    "team_analysis",
]
```

- [ ] **Step 2: 扩展分类 prompt**

在 `router.py` 的 `_CLASSIFY_PROMPT` 末尾追加一行（在 `- data：` 和 `market.fear_greed` 之间）：

```python
- team_analysis：用户要求对某只股票做"全面分析""深入评估""团队分析""多维度评估"，或使用 /team 命令
```

- [ ] **Step 3: 新增 TOOL_GROUPS 条目**

在 `router.py` 的 `TOOL_GROUPS` 字典末尾（`"data"` 条目之后）新增：

```python
    "team_analysis": frozenset(
        {
            "analyze_financial",
            "analyze_risk",
            "technical_snapshot",
            "list_strategy_signals",
            "get_bars_summary",
            "get_quote_context",
            "get_ashare_fear_greed_index",
            "get_stock_notes",
        }
    ),
```

- [ ] **Step 4: 新增关键词兜底**

在 `router.py` 的 `_keyword_fallback` 函数中，在 `_SCREENING_KEYWORDS` 检查之前新增 team_analysis 检查：

```python
    _TEAM_KEYWORDS = (
        "全面分析",
        "深入评估",
        "团队分析",
        "多维度",
        "深度研究",
    )
    if any(k in text for k in _TEAM_KEYWORDS):
        return _with_market("team_analysis")
```

- [ ] **Step 5: 新增 /team 命令预处理**

在 `router.py` 末尾新增函数：

```python
import re as _re

_TEAM_COMMAND = _re.compile(r"^/team\s+(\d{6}(?:\.(?:SSE|SZSE))?)", _re.IGNORECASE)

def normalize_team_command(user_text: str) -> str | None:
    """将 /team 命令展开为自然语言，供路由分类使用。"""
    m = _TEAM_COMMAND.match(user_text.strip())
    if m:
        return f"对 {m.group(1)} 启动团队全面分析"
    return None
```

- [ ] **Step 6: 在 AgentGateway.send 入口处调用 normalize_team_command**

修改 `packages/vnpy-llm/vnpy_llm/gateway/agent_gateway.py`，在 `send` 方法中用户消息进入分类前调用：

找到 `user_text` 的使用位置（约 `self._routing.route(...)` 之前），添加：

```python
from vnpy_llm.routing.router import normalize_team_command
# ...
expanded = normalize_team_command(user_text)
effective_text = expanded if expanded else user_text
# 后续使用 effective_text 替代 user_text 参与路由
```

- [ ] **Step 7: 提交**

```bash
git add packages/vnpy-llm/vnpy_llm/routing/intent.py packages/vnpy-llm/vnpy_llm/routing/router.py packages/vnpy-llm/vnpy_llm/gateway/agent_gateway.py
git commit -m "feat(team): 新增 team_analysis 意图分类与 /team 命令"
```

---

### Task 2: 扩展 AgentName / labels / Supervisor 映射

**Files:**
- Modify: `packages/vnpy-llm/vnpy_llm/graph/state.py`
- Modify: `packages/vnpy-llm/vnpy_llm/graph/supervisor.py`

- [ ] **Step 1: 扩展 AgentName**

修改 `state.py` 第 17 行：

```python
AgentName = Literal[
    "market", "research", "screening", "backtest", "data", "general",
    "financial", "risk", "strategy", "chief",
]
```

- [ ] **Step 2: 新增 CATEGORY_TO_AGENT 映射**

在 `state.py` `CATEGORY_TO_AGENT` 字典末尾新增：

```python
CATEGORY_TO_AGENT: dict[IntentCategory, AgentName] = {
    # ... 现有映射不变
    "team_analysis": "chief",
}
```

- [ ] **Step 3: 新增 AGENT_TOOL_CATEGORIES 映射**

在 `state.py` `AGENT_TOOL_CATEGORIES` 字典末尾新增：

```python
    "financial": frozenset({"team_analysis"}),
    "risk": frozenset({"team_analysis"}),
    "strategy": frozenset({"team_analysis"}),
    "chief": frozenset({"team_analysis"}),
```

- [ ] **Step 4: 新增 AGENT_STREAM_LABELS**

在 `state.py` `AGENT_STREAM_LABELS` 字典末尾新增：

```python
    "financial": "财务面",
    "risk": "风险面",
    "strategy": "策略面",
    "chief": "综合研判",
```

- [ ] **Step 5: 提交**

```bash
git add packages/vnpy-llm/vnpy_llm/graph/state.py
git commit -m "feat(team): 新增 financial/risk/strategy/chief Agent 定义与映射"
```

---

### Task 3: 新增 4 个 Agent Prompt 文件

**Files:**
- Create: `packages/vnpy-llm/vnpy_llm/graph/agents/financial.py`
- Create: `packages/vnpy-llm/vnpy_llm/graph/agents/risk.py`
- Create: `packages/vnpy-llm/vnpy_llm/graph/agents/strategy.py`
- Create: `packages/vnpy-llm/vnpy_llm/graph/agents/chief.py`
- Modify: `packages/vnpy-llm/vnpy_llm/graph/agents/__init__.py`

- [ ] **Step 1: 创建 financial.py**

```python
"""Financial Agent：财务面深度分析。"""

from vnpy_llm.graph.agents.base import register_agent_prompt

FINANCIAL_PROMPT = """【Financial Agent 职责】
负责单只股票的财务深度分析：盈利能力、成长性、偿债能力、估值水平。

工具路由：
→ analyze_financial（tdx-financial-analysis Skill）：
  "财务面怎么样""PE ROE 如何""盈利质量好不好"
→ get_quote_context：需要补充行情信息时

分析维度（必须覆盖）：
- 盈利能力：ROE、毛利率、净利率、扣非净利润同比
- 成长性：营收/利润 CAGR（近 3 年）
- 估值：PE（TTM）、PB、PS，与行业均值对比
- 偿债能力：资产负债率、流动比率

输出格式（**严格要求**）：
1. 先以 Markdown 流式输出分析过程（## 财务面），含评分 + 要点
2. 在回复末尾输出一段 JSON（用 ```json 代码块包裹），格式如下：
```json
{
  "financial": {
    "score": <0-100 整数>,
    "summary": "<一句话总结>",
    "highlights": ["<亮点1>", "<亮点2>"],
    "risks": ["<风险1>", "<风险2>"],
    "raw_data": { "pe": 0.0, "roe": 0.0 }
  }
}
```
评分标准：盈利能力 40 分 + 成长性 25 分 + 估值 20 分 + 偿债 15 分。
禁止编造数据，工具未返回的指标标注 N/A。"""

register_agent_prompt("financial", FINANCIAL_PROMPT)
```

- [ ] **Step 2: 创建 risk.py**

```python
"""Risk Agent：风险面分析。"""

from vnpy_llm.graph.agents.base import register_agent_prompt

RISK_PROMPT = """【Risk Agent 职责】
对单只股票做风险画像：波动率、回撤、Beta、行业风险、市场情绪。

工具路由：
→ analyze_risk（tdx-risk-analysis Skill）：
  "风险怎么样""波动大不大""回撤多少"
→ get_bars_summary：需要 K 线统计时
→ get_ashare_fear_greed_index：需要市场情绪时

分析维度（必须覆盖）：
- 价格风险：年化波动率、最大回撤、下行标准差
- 系统性风险：Beta、与大盘相关性
- 流动性风险：日均成交额、换手率
- 行业风险：所属行业近期表现、政策风险提示
- 市场情绪：恐贪指数，与个股走势对比

输出格式（**严格要求**）：
1. 先以 Markdown 流式输出分析过程（## 风险面），含评分 + 要点
2. 在回复末尾输出一段 JSON（用 ```json 代码块包裹），格式如下：
```json
{
  "risk": {
    "score": <0-100 整数，越低越安全>,
    "summary": "<一句话总结>",
    "highlights": ["<亮点1>", "<亮点2>"],
    "risks": ["<风险1>", "<风险2>"],
    "raw_data": { "volatility": 0.0, "beta": 0.0 }
  }
}
```
评分标准：风险越低分越高（满 100 表示几乎无风险）。
禁止编造数据。"""

register_agent_prompt("risk", RISK_PROMPT)
```

- [ ] **Step 3: 创建 strategy.py**

```python
"""Strategy Agent：策略适配与形态识别。"""

from vnpy_llm.graph.agents.base import register_agent_prompt

STRATEGY_PROMPT = """【Strategy Agent 职责】
对单只股票做策略信号扫描与形态识别。

工具路由：
→ technical_snapshot：技术指标快照（MACD/KDJ/RSI/均线）
→ list_strategy_signals：多策略信号扫描
→ get_bars_summary：K 线概要

分析维度（必须覆盖）：
- 均线状态：MA5/10/20/60/120 排列，多头 or 空头
- MACD/KDJ/RSI 当前状态
- 策略信号匹配：双均线、短线突破、波段回踩、趋势均线等
- 形态识别：W 底、头肩底、老鸭头、均线多头 etc.

输出格式（**严格要求**）：
1. 先以 Markdown 流式输出分析过程（## 策略面），含评分 + 要点
2. 在回复末尾输出一段 JSON（用 ```json 代码块包裹），格式如下：
```json
{
  "strategy": {
    "score": <0-100 整数>,
    "summary": "<一句话总结>",
    "highlights": ["<亮点1>", "<亮点2>"],
    "risks": ["<风险1>", "<风险2>"],
    "raw_data": {}
  }
}
```
评分标准：技术面适配策略的置信度，多头排列+信号共振+形态支持则高分。"""

register_agent_prompt("strategy", STRATEGY_PROMPT)
```

- [ ] **Step 4: 创建 chief.py**

```python
"""Chief Agent：汇总各分析师结论。"""

from vnpy_llm.graph.agents.base import register_agent_prompt

CHIEF_PROMPT = """【Chief Agent 职责】
接收财务、风险、策略三个分析师的结构化输出，整合去重、识别矛盾、生成综合研报。

规则：
- 首先列出分歧点（如财务评分高但风险评分低 → 盈利好但波动大）
- 然后汇总共识点
- 给出综合评分（加权：财务 35% + 风险 25% + 策略 20% + 行情 20%）
  行情维度从终端上下文中获取（现价、涨跌幅、成交量等），无需调用工具
- 最后给出简明结论（描述特征，不买卖建议）

禁止：
- 禁止给出买入/卖出/持有建议
- 禁止编造子分析师未输出的数据
- 某个分析师缺失时，如实说明，不填补

输出格式（Markdown）：
## 📋 综合研判
### 分歧点
### 共识点
### 综合评分（加权：财务 35% + 风险 25% + 策略 20% + 行情 20%）
### 总结"""

register_agent_prompt("chief", CHIEF_PROMPT)
```

- [ ] **Step 5: 修改 agents/__init__.py**

追加 4 行 import：

```python
"""注册各 Specialist Agent 的 prompt 切片。"""

from vnpy_llm.graph.agents import backtest, data, general, market, research, screening
from vnpy_llm.graph.agents import financial, risk, strategy, chief  # 新增
from vnpy_llm.graph.agents.base import build_agent_system_prompt, get_agent_domain_prompt

__all__ = [
    "backtest",
    "build_agent_system_prompt",
    "chief",           # 新增
    "data",
    "financial",       # 新增
    "general",
    "get_agent_domain_prompt",
    "market",
    "research",
    "risk",            # 新增
    "screening",
    "strategy",        # 新增
]
```

- [ ] **Step 6: 提交**

```bash
git add packages/vnpy-llm/vnpy_llm/graph/agents/
git commit -m "feat(team): 新增 financial/risk/strategy/chief Agent prompt 注册"
```

---

### Task 4: 新增 2 个 Skill（工具定义）

**Files:**
- Create: `packages/vnpy-skills/vnpy_skills/financial_analysis_skill.py`
- Create: `packages/vnpy-skills/vnpy_skills/risk_analysis_skill.py`

- [ ] **Step 1: 创建 financial_analysis_skill.py**

```python
"""财务深度分析 Skill。"""

from __future__ import annotations

import json

from vnpy_skills.domain import SkillTemplate, ToolSpec


class FinancialAnalysisSkill(SkillTemplate):
    skill_name = "tdx-financial-analysis"
    author = "zak"
    description = "单票财务深度分析（PE/ROE/毛利率/现金流/杜邦）"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="analyze_financial",
                description=(
                    "对单只股票做财务深度分析。返回盈利能力（ROE/毛利率/净利率/扣非净利润同比）、"
                    "成长性（营收/利润 CAGR 近3年）、估值（PE(TTM)/PB/PS 与行业均值对比）、"
                    "偿债能力（资产负债率/流动比率）。用户问"财务面""PE ROE""盈利质量"时优先调用。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码，如 600519.SSE 或 002230.SZSE",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
        ]

    def _get_analysis_service(self):
        svc = self._services.get("analysis")
        if svc is None:
            raise RuntimeError("AnalysisService 未就绪")
        return svc

    def analyze_financial(self, symbol: str) -> str:
        svc = self._get_analysis_service()
        result = svc.analyze_financial(symbol)
        return json.dumps(result, ensure_ascii=False)
```

- [ ] **Step 2: 创建 risk_analysis_skill.py**

```python
"""风险分析 Skill。"""

from __future__ import annotations

import json

from vnpy_skills.domain import SkillTemplate, ToolSpec


class RiskAnalysisSkill(SkillTemplate):
    skill_name = "tdx-risk-analysis"
    author = "zak"
    description = "单票风险分析（波动率/回撤/Beta/行业风险/市场情绪）"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="analyze_risk",
                description=(
                    "对单只股票做风险画像分析。返回价格风险（年化波动率/最大回撤/下行标准差）、"
                    "系统性风险（Beta/与大盘相关性）、流动性风险（日均成交额/换手率）、"
                    "行业风险（所属行业近期表现）。用户问"风险""波动""回撤"时优先调用。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码，如 600519.SSE 或 002230.SZSE",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
        ]

    def _get_analysis_service(self):
        svc = self._services.get("analysis")
        if svc is None:
            raise RuntimeError("AnalysisService 未就绪")
        return svc

    def analyze_risk(self, symbol: str) -> str:
        svc = self._get_analysis_service()
        result = svc.analyze_risk(symbol)
        return json.dumps(result, ensure_ascii=False)
```

- [ ] **Step 3: 提交**

```bash
git add packages/vnpy-skills/vnpy_skills/
git commit -m "feat(team): 新增 financial/risk analysis Skill 工具定义"
```

---

### Task 5: 新增 TeamOrchestrator 核心引擎

**Files:**
- Create: `packages/vnpy-llm/vnpy_llm/graph/orchestrator.py`

这是核心模块，负责并行调度 3 个子 Agent 各自的 LangGraph ReAct 执行。

- [ ] **Step 1: 创建 orchestrator.py**

```python
"""TeamOrchestrator：并行调度子 Agent + chief 汇总。

编排流程：
1. 用户意图为 team_analysis → 从用户消息中提取 symbol
2. 并行提交 financial / risk / strategy 三个子 Agent 到 ThreadPoolExecutor
3. 主线程按完成顺序 yield 章节标题 + 流式输出
4. 收集结构化 JSON（末尾代码块提取）
5. 全部完成后启动 chief Agent 汇总
"""

from __future__ import annotations

import concurrent.futures
import json
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from vnpy_llm.chat.client import LlmClientError, StreamCancelled
from vnpy_llm.config.settings import LlmConfig
from vnpy_llm.graph.agents.base import build_agent_system_prompt
from vnpy_llm.graph.runner import _conversation_dicts, _stream_agent
from vnpy_llm.graph.state import AGENT_STREAM_LABELS, AgentName, GraphStreamContext

# 子 Agent 超时秒数
AGENT_TIMEOUT_SECONDS = 30
# 至少需要完成的子 Agent 数量才启动 chief 汇总
MIN_COMPLETED_AGENTS = 2

# team 模式需从用户消息中提取 symbol 的正则
_SYMBOL_PATTERN = re.compile(r"(\d{6}(?:\.(?:SSE|SZSE|SH|SZ)))", re.IGNORECASE)

# 子 Agent 工具分配表
TEAM_AGENT_TOOLS: dict[AgentName, frozenset[str]] = {
    "financial": frozenset({"analyze_financial", "get_quote_context"}),
    "risk": frozenset({"analyze_risk", "get_bars_summary", "get_ashare_fear_greed_index"}),
    "strategy": frozenset({"technical_snapshot", "list_strategy_signals", "get_bars_summary"}),
}

# 子 Agent 执行顺序（并行，此处仅定义集合）
TEAM_AGENTS: tuple[AgentName, ...] = ("financial", "risk", "strategy")


@dataclass
class AgentResult:
    agent: AgentName
    markdown: str = ""
    json_data: dict[str, Any] | None = None
    error: str | None = None
    timed_out: bool = False


def _extract_symbol(text: str) -> str | None:
    """从用户消息中提取股票代码。"""
    m = _SYMBOL_PATTERN.search(text)
    if not m:
        return None
    raw = m.group(1).upper()
    # 规范化后缀
    if raw.endswith(".SH"):
        raw = raw.replace(".SH", ".SSE")
    if raw.endswith(".SZ"):
        raw = raw.replace(".SZ", ".SZSE")
    return raw


def _filter_tools_for_team_agent(
    agent: AgentName,
    all_tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """按 TEAM_AGENT_TOOLS 过滤该子 Agent 的可用工具。"""
    allowed = TEAM_AGENT_TOOLS.get(agent, frozenset())
    if not allowed:
        return []
    return [
        tool
        for tool in all_tools
        if (tool.get("function") or {}).get("name", "") in allowed
    ]


def _extract_json_from_text(text: str) -> dict[str, Any] | None:
    """从 Agent 输出末尾提取 ```json 代码块。"""
    pattern = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
    matches = pattern.findall(text)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def _run_single_agent(
    agent: AgentName,
    symbol: str,
    messages: list[dict[str, Any]],
    all_tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], str],
    config: LlmConfig,
    graph_ctx: GraphStreamContext,
    max_rounds: int,
    should_cancel: Callable[[], bool] | None,
) -> AgentResult:
    """在线程中执行单个子 Agent 的 ReAct 任务，返回 AgentResult。"""
    result = AgentResult(agent=agent)
    try:
        tools = _filter_tools_for_team_agent(agent, all_tools)
        system = build_agent_system_prompt(agent, graph_ctx)
        agent_messages = [{"role": "system", "content": system}, *messages]

        chunks: list[str] = []
        for delta in _stream_agent(
            config,
            agent_messages,
            tools,
            tool_executor,
            max_rounds=max_rounds,
            should_cancel=should_cancel,
        ):
            chunks.append(delta)

        result.markdown = "".join(chunks)
        result.json_data = _extract_json_from_text(result.markdown)
    except StreamCancelled:
        result.error = "用户取消"
    except Exception as ex:
        result.error = str(ex)

    return result


def _build_team_context_for_chief(
    results: dict[AgentName, AgentResult],
    context_text: str,
) -> str:
    """构建 chief Agent 的上下文：子 Agent 输出 + 行情。"""
    parts = ["【子分析师输出】"]
    for agent_name in TEAM_AGENTS:
        r = results.get(agent_name)
        if r is None:
            parts.append(f"\n### {AGENT_STREAM_LABELS.get(agent_name, agent_name)}\n（未执行）")
        elif r.error:
            parts.append(f"\n### {AGENT_STREAM_LABELS.get(agent_name, agent_name)}\n（异常：{r.error}）")
        elif r.timed_out:
            parts.append(f"\n### {AGENT_STREAM_LABELS.get(agent_name, agent_name)}\n（超时未完成）")
        else:
            parts.append(f"\n### {AGENT_STREAM_LABELS.get(agent_name, agent_name)}\n{r.markdown}")

    if context_text.strip():
        parts.append(f"\n【行情上下文】\n{context_text.strip()}")

    parts.append("\n请根据以上子分析师的输出和行情上下文，生成综合研判。")
    return "\n".join(parts)


def stream_team_analysis(
    config: LlmConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], str],
    *,
    max_rounds: int = 3,
    should_cancel: Callable[[], bool] | None = None,
    graph_ctx: GraphStreamContext,
    all_tools: list[dict[str, Any]] | None = None,
) -> Iterator[str]:
    """团队并行分析入口。"""
    if not config.configured:
        raise LlmClientError("未配置 LLM_API_KEY，请在 .env 中设置")

    symbol = _extract_symbol(graph_ctx.user_text)
    if not symbol:
        raise LlmClientError("未识别到股票代码，请提供如 /team 600519 或"全面分析 600519"")

    full_tools = all_tools or tools
    conversation = _conversation_dicts(messages)

    # 添加用户消息提示
    team_user_msg = {
        "role": "user",
        "content": f"请对 {symbol} 做你负责维度的分析，先输出 Markdown 分析过程，最后输出 JSON 结构。",
    }
    agent_messages = [*conversation, team_user_msg]

    # 进度提示
    agent_names_str = "、".join(AGENT_STREAM_LABELS.get(a, a) for a in TEAM_AGENTS)
    yield f"\n🔄 分析团队已启动：{agent_names_str}（并行分析中...）\n\n"

    # 并行执行
    results: dict[AgentName, AgentResult] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(TEAM_AGENTS)) as executor:
        future_map: dict[concurrent.futures.Future[AgentResult], AgentName] = {}
        for agent in TEAM_AGENTS:
            future = executor.submit(
                _run_single_agent,
                agent,
                symbol,
                agent_messages,
                full_tools,
                tool_executor,
                config,
                graph_ctx,
                max_rounds,
                should_cancel,
            )
            future_map[future] = agent

        # 按完成顺序收集结果
        for future in concurrent.futures.as_completed(future_map, timeout=AGENT_TIMEOUT_SECONDS):
            agent = future_map[future]
            try:
                result = future.result()
            except concurrent.futures.TimeoutError:
                result = AgentResult(agent=agent, timed_out=True)
            except Exception as ex:
                result = AgentResult(agent=agent, error=str(ex))

            results[agent] = result

            # 流式输出该子 Agent 的标题和内容
            label = AGENT_STREAM_LABELS.get(agent, agent)
            if result.error:
                yield f"\n**{label}** ⚠️ 分析异常：{result.error}\n\n"
            elif result.timed_out:
                yield f"\n**{label}** ⏱️ 分析超时\n\n"
            else:
                yield f"\n## {label}\n\n"
                yield result.markdown
                yield "\n"

    # 补充超时的 Agent
    for agent in TEAM_AGENTS:
        if agent not in results:
            results[agent] = AgentResult(agent=agent, timed_out=True)

    # 统计完成数
    completed = sum(
        1 for r in results.values() if not r.error and not r.timed_out and r.markdown
    )
    if completed < MIN_COMPLETED_AGENTS:
        yield "\n⚠️ 分析团队完成率不足（{}/{}），无法生成综合研判。请稍后重试。\n".format(
            completed, len(TEAM_AGENTS)
        )
        return

    # chief 汇总
    yield "\n---\n"

    chief_context = _build_team_context_for_chief(results, graph_ctx.context_text)
    chief_messages = [
        {
            "role": "system",
            "content": build_agent_system_prompt("chief", graph_ctx),
        },
        *conversation,
        {"role": "user", "content": chief_context},
    ]

    # chief 无工具（纯文本汇总）
    try:
        for delta in _stream_agent(
            config,
            chief_messages,
            [],
            tool_executor,
            max_rounds=max_rounds,
            should_cancel=should_cancel,
        ):
            yield delta
    except StreamCancelled:
        raise
    except Exception as ex:
        raise LlmClientError(f"综合研判生成失败: {ex}") from ex
```

- [ ] **Step 2: 提交**

```bash
git add packages/vnpy-llm/vnpy_llm/graph/orchestrator.py
git commit -m "feat(team): 新增 TeamOrchestrator 并行编排引擎"
```

---

### Task 6: runner.py 与 AgentRuntime 分支切换

**Files:**
- Modify: `packages/vnpy-llm/vnpy_llm/graph/runner.py`（import orchestrator）
- Modify: `packages/vnpy-llm/vnpy_llm/gateway/agent_runtime.py`（分支判断）

- [ ] **Step 1: 修改 agent_runtime.py 增加 team 分支**

在 `stream_deltas` 方法开头增加 team 判断：

```python
from vnpy_llm.graph.orchestrator import stream_team_analysis

class AgentRuntime:
    @staticmethod
    def stream_deltas(
        config: LlmConfig,
        *,
        all_tools: list[dict[str, Any]],
        conversation_messages: list[dict[str, str]],
        api_messages: list[dict[str, str]],
        route_ctx: RouteContext | None,
        graph_ctx: GraphStreamContext | None,
        mcp_tool_names: frozenset[str],
        tool_executor: Callable[[str, dict[str, Any]], str],
        should_cancel: Callable[[], bool] | None = None,
        on_handoff: Callable[[str, str, str], None] | None = None,
    ) -> Iterator[str]:
        # 团队模式分支
        if graph_ctx is not None and graph_ctx.analysis.route.category == "team_analysis":
            yield from stream_team_analysis(
                config,
                conversation_messages,
                route_ctx.tools if route_ctx else [],
                tool_executor,
                should_cancel=should_cancel,
                graph_ctx=graph_ctx,
                all_tools=all_tools,
            )
            return

        if all_tools and route_ctx is not None and graph_ctx is not None:
            yield from stream_with_tools(
                config,
                conversation_messages,
                route_ctx.tools,
                tool_executor,
                should_cancel=should_cancel,
                graph_ctx=graph_ctx,
                all_tools=all_tools,
                mcp_tool_names=mcp_tool_names,
                on_handoff=on_handoff,
            )
            return
        yield from stream_chat_completion(
            config,
            api_messages,
            should_cancel=should_cancel,
        )
```

- [ ] **Step 2: 提交**

```bash
git add packages/vnpy-llm/vnpy_llm/gateway/agent_runtime.py
git commit -m "feat(team): AgentRuntime 新增 team_analysis 分支路由"
```

---

### Task 7: AnalysisService 扩展（analyze_financial / analyze_risk / analyze_strategy）

**Files:**
- Modify: `packages/vnpy-ashare/vnpy_ashare/services/analysis_service.py`

- [ ] **Step 1: 在 AnalysisService 类中新增 3 个方法**

在 `diagnose` 方法之后追加：

```python
    def analyze_financial(self, symbol: str) -> dict[str, Any]:
        """财务深度分析：PE/ROE/毛利率/净利润同比/营收CAGR/估值对比。

        注：首期返回基础框架结构，数据从 bar_store 和 quote 合并；后续接入 Tushare 财务接口补全。
        """
        try:
            item = parse_stock_symbol(symbol)
        except Exception:
            item = None

        name = item.name if item else symbol
        bar_summary = self._engine.bar_service.get_bars_summary(symbol)
        quote = self._engine.quote_service.get_quote_snapshot(symbol)

        return {
            "symbol": symbol,
            "name": name,
            "provider": "zak-financial-v1",
            "pe": getattr(quote, "pe", None) if quote else None,
            "pb": getattr(quote, "pb", None) if quote else None,
            "market_cap": getattr(quote, "total_market_cap", None) if quote else None,
            "industry": getattr(quote, "industry", "") if quote else "",
            "bar_count": bar_summary.get("count", 0) if bar_summary else 0,
            "data_availability": {
                "roe": False,
                "gross_margin": False,
                "net_profit_yoy": False,
                "revenue_cagr_3y": False,
                "debt_ratio": False,
                "current_ratio": False,
            },
            "note": "财务详细数据依赖 Tushare 接口，当前返回基础估值信息。",
        }

    def analyze_risk(self, symbol: str) -> dict[str, Any]:
        """风险分析：波动率/回撤/Beta/流动性。

        注：首期从 K 线概要计算基础波动率和回撤；Beta 和下行标准差后续补全。
        """
        try:
            item = parse_stock_symbol(symbol)
        except Exception:
            item = None

        name = item.name if item else symbol
        bar_summary = self._engine.bar_service.get_bars_summary(symbol)

        return {
            "symbol": symbol,
            "name": name,
            "provider": "zak-risk-v1",
            "bar_count": bar_summary.get("count", 0) if bar_summary else 0,
            "volatility_annualized": None,
            "max_drawdown": None,
            "downside_std": None,
            "beta": None,
            "avg_volume": None,
            "avg_turnover": None,
            "data_availability": {
                "volatility": False,
                "max_drawdown": False,
                "beta": False,
                "liquidity": False,
            },
            "note": "风险指标依赖 K 线计算，当前返回基础框架。",
        }

    def analyze_strategy(self, symbol: str) -> dict[str, Any]:
        """策略适配分析：复用 technical_snapshot + strategy_signals。"""
        technical = self.technical_snapshot(symbol)
        signals = self.strategy_signals(symbol)

        return {
            "symbol": symbol,
            "provider": "zak-strategy-v1",
            "technical": technical,
            "strategy_signals": signals,
        }
```

- [ ] **Step 2: 提交**

```bash
git add packages/vnpy-ashare/vnpy_ashare/services/analysis_service.py
git commit -m "feat(team): AnalysisService 新增 analyze_financial/risk/strategy 方法"
```

---

### Task 8: SKILL.md 文档 + 端到端验证

**Files:**
- Create: `skills/tdx-financial-analysis/SKILL.md`
- Create: `skills/tdx-risk-analysis/SKILL.md`

- [ ] **Step 1: 创建 tdx-financial-analysis SKILL.md**

```md
# 财务深度分析 Skill

通过 zak 终端内置的 `analyze_financial` Skill 工具执行单票财务分析。

## 工具

- `analyze_financial(symbol="600519.SSE")`

## 返回维度

- **估值**：PE(TTM)、PB、PS
- **盈利能力**：ROE、毛利率、净利率、扣非净利润同比
- **成长性**：营收/利润 CAGR（近 3 年）
- **偿债能力**：资产负债率、流动比率

## 注意事项

- 数据来源：Tushare 财务接口（需配置 Tushare Token）
- 返回值包含 `data_availability` 标记各维度数据是否可用
- 数据缺失时如实说明，禁止编造
```

- [ ] **Step 2: 创建 tdx-risk-analysis SKILL.md**

```md
# 风险分析 Skill

通过 zak 终端内置的 `analyze_risk` Skill 工具执行单票风险画像。

## 工具

- `analyze_risk(symbol="600519.SSE")`

## 返回维度

- **价格风险**：年化波动率、最大回撤、下行标准差
- **系统性风险**：Beta、与大盘相关性
- **流动性风险**：日均成交额、换手率
- **行业风险**：所属行业近期表现

## 注意事项

- 数据来源：本地 K 线计算
- 需要至少 60 根日 K 线才能计算有效指标
- K 线不足时返回 `data_availability` 为空
```

- [ ] **Step 3: 提交**

```bash
git add skills/tdx-financial-analysis/ skills/tdx-risk-analysis/
git commit -m "docs(team): 新增 financial/risk analysis SKILL.md 文档"
```
