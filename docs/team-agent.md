# 智能体投研团队

> 编排：`vnpy_llm/graph/orchestrator.py` · 路由见 [ai-data-routing.md](./ai-data-routing.md)

对单只股票并行财务 / 风险 / 策略分析，由 chief 汇总研报。与现有「单 Agent 意图路由」互补，不替代 `diagnose_stock` 快速诊断。

## 用户入口

| 方式 | 示例 |
|------|------|
| 自然语言 | 「全面分析 600519」「对这只票做团队分析」 |
| 显式命令 | `/team 600519` 或 `/team 600519.SSE` |
| 深度模式 | AI 对话面板勾选「深度投研团队」；QSettings `llm/team_deep_mode` 或 env `LLM_TEAM_DEEP_MODE` |

与 [`diagnose_stock`](../skills/tdx-stock-diagnose/SKILL.md)（问小达单轮概览）互补——团队模式分维度深挖。

## 架构

```
用户输入 → IntentCategory == team_analysis
              │
              ▼
         TeamOrchestrator.stream_team_analysis
              ├─ prefetch_team_facts（问小达 + 本地结构化数据）
              ├─ 快速模式：预取 ≥2 维 → 直接出章节 + chief
              ├─ 深度模式：ThreadPoolExecutor 并行 financial / risk / strategy ReAct
              └─ chief 汇总 → 可选落库 stock_analysis_reports（zak://team-report 链接）

其它 category → 现有 stream_with_tools / handoff（不变）
```

触发：`/team` 命令、关键词（全面分析 / 团队分析 / 多维度 / 深度研究）或 LLM 分类。`team_analysis` **不走** handoff。

入口分支：`AgentRuntime.stream_deltas`（`gateway/agent_runtime.py`）。

## 快速模式 vs 深度模式

启动前 `AnalysisService.prefetch_team_facts()` 并行预取，写入 `graph_ctx.team_prefetch`。

| 模式 | 条件 | 行为 |
|------|------|------|
| **快速**（默认） | 预取 ≥2/3 维可用，且未勾选「深度投研团队」 | 用预取数据生成各章节，跳过子 Agent ReAct，chief 汇总 |
| **深度** | 勾选深度模式或预取不足 2 维 | 并行 ReAct（各 Agent 最多 3 轮工具，单 Agent 超时 60s） |

预取不足时自动降级深度模式并提示。配置热加载见 [config-hot-reload.md](./config-hot-reload.md)。

## 子 Agent 与工具

| Agent | 职责 | 工具 |
|-------|------|------|
| financial | 盈利、成长、估值、偿债 | `analyze_financial`, `get_quote_context` |
| risk | 波动、回撤、Beta、流动性、情绪 | `analyze_risk`, `get_bars_summary`, `get_ashare_fear_greed_index` |
| strategy | 均线、指标、策略信号、形态 | `technical_snapshot`, `list_strategy_signals`, `get_bars_summary` |
| chief | 分歧 / 共识、加权综合研判 | 无工具；行情从 context 注入 |

预取 `strategy` 维度含 **`ultra_short`** 块：情绪阶段、打板/突破信号；规则评分见 `graph/team_scoring.py`。

chief 加权：财务 35% + 风险 25% + 策略 20% + 行情 20%。禁止买卖建议；至少 2/3 子 Agent 完成才汇总。

子 Agent 深度模式下产出 Markdown + 末尾 JSON 评分（`graph/team_schema.py` 约束）。

## 研报落库

chief 输出含「综合研判」时，`persist_team_analysis_report()` 写入 `stock_analysis_reports`（`source_scope=team_analysis`），对话末尾追加 `zak://team-report/{id}`，可在笔记中心报告 Tab 打开。见 [stock-notes.md](./stock-notes.md)。

## Skill 实现

| Skill | 工具 | 实现 |
|-------|------|------|
| tdx-financial-analysis | `analyze_financial` | `skills/financial_analysis_skill.py` |
| tdx-risk-analysis | `analyze_risk` | `skills/risk_analysis_skill.py` |
| tdx-stock-diagnose | `diagnose_stock`（快速诊断，非团队路径） | `skills/tdx_diagnose_skill.py` |

数据：`analyze_financial` → Tushare / 行情；`analyze_risk` → 本地 K 线（不足时 `data_availability` 标 false）。

## 与 diagnose_stock 对比

| | 快速诊断 | 团队分析 |
|---|----------|----------|
| 工具 | `diagnose_stock` | `team_analysis` 编排 |
| 深度 | 问小达四维度概览 | 分 Agent 深挖 + chief |
| 典型场景 | 「诊断一下」「这票怎么样」 | 「全面分析」「/team 600519」 |

## 后续演进

- portfolio Agent（持仓维度，待持仓模块完善）
- Tushare 补全 `analyze_financial` 全量财务指标
- K 线衍生补全 `analyze_risk`（Beta、下行标准差等）

## 关键代码

| 模块 | 路径 |
|------|------|
| 编排器 | `packages/vnpy-llm/vnpy_llm/graph/orchestrator.py` |
| 预取 / 评分 | `services/analysis.py`, `graph/team_scoring.py` |
| 研报落库 | `services/analysis_detail/team_report.py` |
| 路由 | `routing/intent.py`, `routing/router.py` |
| Agent prompt | `graph/agents/financial.py`, `risk.py`, `strategy.py`, `chief.py` |
