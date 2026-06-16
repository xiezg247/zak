# 智能体投研团队设计方案

> 状态：待实施 | 创建：2026-06-16

## 1. 背景与动机

### 1.1 现状

zak 现有 Agent 体系是**意图路由模型**——用户输入 → LLM 分类 → 路由到单个 Specialist Agent 回答，至多通过关键词匹配追加 1 个 market Agent 做 handoff。

现有 Agent 列表：market、research、screening、backtest、data、general。

### 1.2 问题

- 个股分析是孤立的——`research` 通吃行情+技术面+基本面+资金面，缺乏深度
- 没有风险维度——风控分析完全空白
- 结果没有串起来——各 Agent 独立输出，缺少跨维度综合研判
- 没有持仓分析——现有系统偏"看和选"而非"管"

### 1.3 目标

新增**团队协作模式**：对单只股票同时启动财务、风险、策略 3 个分析师并行工作，由总分析师汇总输出结构化研报。与现有「单 Agent 路由」是互补模式。

---

## 2. 方案选择

### 方案对比

| | 方案 A：单 Agent 分段 | 方案 B：并行子 Agent + 总分析师（选择） | 方案 C：串行链式传递 |
|---|---|---|---|
| 复杂度 | 低 | 中 | 低 |
| 响应速度 | 慢（串行） | 快（并行） | 最慢（严格串行） |
| 分析深度 | 不稳定 | 深（各司其职+独立工具） | 中等 |
| 扩展性 | 差 | 好（加 Agent 即注册） | 一般 |
| Token 消耗 | 低 | 中等 | 中等 |

**选择方案 B**：项目已有成熟的 Agent 注册、工具过滤、LangGraph ReAct 基础设施，并行编排是对现有架构的自然扩展。

---

## 3. 总体架构

### 3.1 双路径并存的编排模型

```
用户输入
  │
  ▼
IntentAnalysis（LLM 意图分类）
  │
  ├─ category == "team_analysis"
  │   │
  │   ▼
  │ TeamOrchestrator（新模块）
  │   ├─ 并行启动 3 个子 Agent
  │   │   ├─ financial → 财务分析
  │   │   ├─ risk → 风险分析
  │   │   └─ strategy → 策略适配
  │   ├─ 收集结构化 JSON 输出
  │   └─ chief Agent → 汇总研报
  │
  └─ 其他 category → 现有路径（不改变）
      └─ SupervisorDecision → target_agent → handoff_agents
```

### 3.2 触发方式

- **自动判断**：LLM 分类器识别"全面分析""深入评估""团队分析""多维度评估"等意图
- **显式命令**：`/team 600519` → 展开为自然语言后走自动路由

### 3.3 与现有架构的关系

- 现有 `stream_with_tools`（串行链）保持不变
- 新增 `stream_team_analysis`（并行扇出+汇总），走独立路径
- 在 `AgentRuntime.stream_deltas` 入口处按意图分支

---

## 4. 并行编排器 TeamOrchestrator

### 4.1 并行策略

使用 `concurrent.futures.ThreadPoolExecutor`（max_workers=3），原因：
- LangGraph 的 `graph.stream()` 是同步的，在线程中执行最自然
- 避免阻塞 Qt 事件循环

```
TeamOrchestrator.stream_team()
  ├─ 创建 ThreadPoolExecutor(3)
  ├─ submit 3 个 future（financial / risk / strategy）
  ├─ 主线程轮询 future.done()，按完成顺序 yield 章节标题
  └─ 全部完成后，启动 chief Agent 汇总
```

### 4.2 子 Agent 执行规格

每个子 Agent 执行**单轮 ReAct 任务**（最多 3 轮工具调用），产出**结构化 JSON**：

```python
@dataclass
class TeamAgentTask:
    agent: AgentName          # "financial" | "risk" | "strategy"
    symbol: str               # 如 "600519.SSE"
    system_prompt: str        # 拼装好的完整 system prompt
    tools: list[dict]         # 该 Agent 专用工具子集
    max_rounds: int = 3       # 工具调用上限
```

**输出格式**：每个子 Agent 产出两部分内容：
1. **流式 Markdown**（用户可见）—— 分析过程与结论，实时流式展示
2. **末尾 JSON**（orchestrator 解析）—— 结构化评分与要点，供 chief 汇总

末尾 JSON 格式（在 system prompt 中约束）：

```json
{
  "financial": {
    "score": 78,
    "summary": "盈利能力稳健，ROE 连续 3 年 >15%...",
    "highlights": ["ROE 15.2%", "毛利率 48%"],
    "risks": ["应收账款周转率下降"],
    "raw_data": {}
  },
  "risk": {
    "score": 65,
    "summary": "中等风险，近期波动率偏高...",
    "highlights": ["年化波动率 28%", "Beta 1.2"],
    "risks": ["下行风险偏大"],
    "raw_data": {}
  },
  "strategy": {
    "score": 72,
    "summary": "均线多头排列，短线有信号...",
    "highlights": ["站上 MA20/MA60"],
    "risks": ["MACD 高位钝化"],
    "raw_data": {}
  }
}
```

### 4.3 工具分配

每个子 Agent 拥有独立工具子集，互不重叠：

| Agent | 可用工具 | 来源 |
|-------|---------|------|
| financial | `analyze_financial`(新)、`get_quote_context` | 新增 Skill + 现有 |
| risk | `analyze_risk`(新)、`get_bars_summary`、`get_ashare_fear_greed_index` | 新增 Skill + 现有 |
| strategy | `technical_snapshot`、`list_strategy_signals`、`get_bars_summary` | 现有工具 |

### 4.4 流式输出编排

用户看到的效果：

1. 先显示"分析团队已启动：财务分析、风险分析、策略分析（并行）"
2. 按完成顺序流式展示各章节（各 Agent 的 Markdown 输出）
3. 全部完成后启动 chief 汇总

### 4.5 错误与超时处理

- 单 Agent 超时 30s → 标记为 "timeout"，不阻塞其他
- 至少 2/3 完成才启动 chief 汇总
- 全部超时 → 降级回单 Agent 诊断模式
- 单 Agent 异常 → 记录异常，chief 汇总时说明"XX 分析师暂不可用"
- 用户停止 → 取消所有 running future，抛出 `StreamCancelled`

---

## 5. Agent 定义

### 5.1 financial（财务分析师）

**职责**：盈利能力、成长性、估值、偿债能力深度分析。

**分析维度**：
- 盈利能力：ROE、毛利率、净利率、扣非净利润同比
- 成长性：营收/利润 CAGR（近 3 年）
- 估值：PE(TTM)、PB、PS，与行业均值对比
- 偿债能力：资产负债率、流动比率

**工具**：`analyze_financial`（新增 Skill）、`get_quote_context`

**输出**：Markdown 格式，「财务面」标题 + 评分 + 要点。

### 5.2 risk（风险分析师）

**职责**：波动率、回撤、Beta、行业风险、市场情绪。

**分析维度**：
- 价格风险：年化波动率、最大回撤、下行标准差
- 系统性风险：Beta、与大盘相关性
- 流动性风险：日均成交额、换手率
- 行业风险：所属行业近期表现、政策风险提示
- 市场情绪：恐贪指数，与个股走势对比

**工具**：`analyze_risk`（新增 Skill）、`get_bars_summary`、`get_ashare_fear_greed_index`

**输出**：Markdown 格式，「风险面」标题 + 评分 + 要点（风险评分越低越好）。

### 5.3 strategy（策略分析师）

**职责**：策略信号扫描与形态识别。

**分析维度**：
- 均线状态：MA5/10/20/60/120 排列
- MACD/KDJ/RSI 当前状态
- 策略信号匹配：双均线、短线突破、波段回踩、趋势均线
- 形态识别：W 底、老鸭头、均线多头

**工具**：`technical_snapshot`、`list_strategy_signals`、`get_bars_summary`

**输出**：Markdown 格式，「策略面」标题 + 评分 + 要点。

### 5.4 chief（总分析师）

**职责**：整合三个子分析师输出，识别矛盾，生成综合研报。

**规则**：
- 列出分歧点（如财务评分高但风险评分低 → 盈利好但波动大）
- 汇总共识点
- 综合评分（加权：财务 35% + 风险 25% + 策略 20% + 行情 20%）
  - 行情维度由 orchestrator 从 context_store 注入 chief 的 context_text（现价、涨跌幅、成交量等），chief 无需单独调用工具
- 简明结论（描述特征，不买卖建议）

**输出**：Markdown 格式，「综合研判」标题 + 分项。

### 5.5 与现有 `research` Agent 的关系

| 工具 | 模式 | 深度 | 适用 |
|------|------|------|------|
| `diagnose_stock` | 单 Agent 快速诊断 | 浅（4 维度概览） | 快速了解、轻量查询 |
| Team 模式 | 3 Agent 并行深挖 | 深（每个维度独立 ReAct） | 深入评估、决策参考 |

两者不互斥——保留 `diagnose_stock` 用于快速诊断场景。

---

## 6. 路由与联动

### 6.1 IntentCategory 扩展

新增 `"team_analysis"`：

```python
IntentCategory = Literal[
    ...,
    "team_analysis",  # 新增：团队全面分析
]
```

### 6.2 分类逻辑

LLM 分类 prompt 增加：
> team_analysis：用户要求对某只股票做"全面分析""深入评估""团队分析""多维度评估"，或使用 `/team` 命令

关键词兜底：
```python
_TEAM_KEYWORDS = ("全面分析", "深入评估", "团队分析", "多维度", "深度研究")
```

### 6.3 `/team` 命令

预处理阶段展开：`/team 600519` → "对 600519.SSE 启动团队全面分析"

### 6.4 Supervisor 映射

```python
CATEGORY_TO_AGENT["team_analysis"] = "chief"
# chief 收到请求后由 orchestrator 级联启动子 Agent
```

### 6.5 TOOL_GROUPS

```python
"team_analysis": frozenset({
    "analyze_financial", "analyze_risk",
    "technical_snapshot", "list_strategy_signals",
    "get_bars_summary", "get_quote_context",
    "get_ashare_fear_greed_index", "get_stock_notes",
})
```

### 6.6 与 handoff 的关系

`team_analysis` 不走 handoff——团队模式内部已覆盖市场情绪和技术面。

---

## 7. 新增 Skill

### 7.1 tdx-financial-analysis

- **文件**：`packages/vnpy-skills/vnpy_skills/financial_analysis_skill.py`
- **工具**：`analyze_financial(symbol)`
- **数据来源**：Tushare 财务接口，通过 `analysis_service.analyze_financial()` 实现

### 7.2 tdx-risk-analysis

- **文件**：`packages/vnpy-skills/vnpy_skills/risk_analysis_skill.py`
- **工具**：`analyze_risk(symbol)`
- **数据来源**：本地 K 线（波动率/回撤/Beta）+ 恐贪指数 + 行业数据

---

## 8. 首期范围

### 包含

- financial / risk / strategy 三个子 Agent
- chief 总分析师
- TeamOrchestrator 并行编排引擎
- `/team` 命令 + 自动意图识别
- 2 个新 Skill（financial + risk analysis）
- AnalysisService 扩展（3 个新方法）

### 不包含

- portfolio（持仓）Agent——待持仓模块完善后加入
- UI 面板改动——首期用现有对话面板流式展示

---

## 9. 文件改动清单

| 文件 | 改动 | 估计行数 |
|------|------|---------|
| `routing/intent.py` | 新增 category | +1 |
| `routing/router.py` | 分类 prompt + TOOL_GROUPS + 关键词 + `/team` 命令 | +25 |
| `graph/state.py` | 4 个 AgentName + labels + 映射 | +12 |
| `graph/supervisor.py` | team → chief 映射 | +1 |
| `graph/agents/financial.py` | **新文件** | ~25 |
| `graph/agents/risk.py` | **新文件** | ~25 |
| `graph/agents/strategy.py` | **新文件** | ~25 |
| `graph/agents/chief.py` | **新文件** | ~30 |
| `graph/agents/__init__.py` | 新增 import | +4 |
| `graph/orchestrator.py` | **新文件，核心引擎** | ~200 |
| `graph/runner.py` | 新增 `stream_team_analysis` | +80 |
| `gateway/agent_runtime.py` | 分支判断 | +5 |
| `gateway/routing_plane.py` | 上下文透传 | +3 |
| `vnpy_skills/financial_analysis_skill.py` | **新文件** | ~35 |
| `vnpy_skills/risk_analysis_skill.py` | **新文件** | ~35 |
| `services/analysis_service.py` | 3 个新分析方法 | +60 |
| `skills/tdx-financial-analysis/SKILL.md` | **新文件** | ~40 |
| `skills/tdx-risk-analysis/SKILL.md` | **新文件** | ~40 |

**总计**：18 个文件，新增 ~650 行，修改 ~50 行。
