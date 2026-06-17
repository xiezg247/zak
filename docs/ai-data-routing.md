# AI 数据路由

AI 助手各类问题对应的数据来源与工具。运行 `uv run python cli.py tools mcp-list` 可列出通达信 MCP 工具。

各功能域对**本地日 K** 的依赖程度、下载范围建议见 [AI 功能与 K 线](./ai-kline-data.md)。

## 编排入口（AgentGateway）

对话编排经 `vnpy_llm.gateway.AgentGateway.send` 统一入口：

1. **RoutingPlane**（`gateway/routing_plane.py`）→ 合并 `routing/router` 意图分类与 `graph/supervisor` 委派，产出 `RoutingDecision`
2. **AgentRuntime**（`gateway/agent_runtime.py`）→ `team_analysis` 走 `graph/orchestrator.stream_team_analysis`；其余有工具走 `graph/runner.stream_with_tools`，无工具走 `chat/client.stream_chat_completion`
3. **ReAct loop**（`langchain.agents.create_agent`）→ `ToolRegistry` 执行 Skill / MCP
4. **Handoff**（`graph/handoff.py`）→ 诊断/回测/选股若涉及大盘或技术面，串行追加 market Agent；段间以 `**市场环境**` 等标题分隔（`team_analysis` 不走 handoff）
5. **选股执行** → `propose_screening` / `propose_recipe` 解析后由 Skill 直接执行（无弹窗确认）

`LlmEngine` 仅作 VeighNa 插件与 Qt 信号桥接；详见 [architecture.md](./architecture.md#agentgateway-控制面)。

无工具闲聊的 system prompt 由 `ContextAssembler` 拼装（`routing/prompts.py` 与 `routing/base_prompt.py`）。

LLM **不直接调用** `mcp_*`；综合诊断经 `diagnose_stock` Skill 访问通达信 MCP。

## 路由总表

| 用户意图 | 工具 / 数据源 | 降级 |
|----------|---------------|------|
| 当前选中标的 | `get_quote_context` | — |
| 本地 K 线 / 区间涨跌 | `get_bars_summary` / `get_bars_data` | 提示下载日 K |
| 近期走势 / 历史统计 | `historical_pattern_summary` | 本地不足时问小达 MCP 兜底 |
| 技术面快照 | `technical_snapshot` | 提示下载日 K |
| 快速综合诊断 | `diagnose_stock` | 问小达 MCP |
| 团队全面分析 | `team_analysis` → 预取 + 快速/深度双模式 + chief | 预取不足自动深度；研报落笔记中心 |
| 财务深度 | `analyze_financial` | Tushare；缺失维度标 N/A |
| 风险画像 | `analyze_risk` | 本地 K 线计算；不足时标 N/A |
| 实时行情 / 板块 | 通达信 MCP `mcp_tdx_*` | TickFlow / Redis |
| 财务 / 估值 / 宏观 | `tushare-data` Skill | — |
| 选股结果解读 | `explain_screening_run` / `get_screening_context` | 选股页运行方案 |
| 走势预测 / 情景分析 | `trend_scenario_summary` + `mcp_tdx_tdx_wenda_quotes` | 本地 K 不足时提示下载日 K |
| 回测解读 | `get_backtest_result` / `list_backtest_history` | — |
| 情绪 / 择时（规划） | `get_emotion_cycle` | T-03 未建时降级恐贪 + 广度文案 |
| 龙头选股（规划） | `run_leader_screen` | 依赖雷达 `leader_pick` 刷新 |
| 风控闸 | `check_risk_gate` ✅ | 账户闸 + 情绪周期合并 |
| 次日计划（规划） | `propose_trading_plan` | 用户确认后写入 `trading_plans` |
| 交易流水（规划） | `get_trade_journal` | J-02 表未建时仅读笔记流水 |
| 买点模式评估 | `evaluate_entry_mode` ✅ | 单票 + 情绪阶段 |

## 择时与短线工具（规划）

> ID 与状态见 [implementation-roadmap.md §10](./implementation-roadmap.md#10-ai-工具a-)。**未实现前** Agent 不得编造阶段标签，须声明能力缺失并降级现有工具。

| 用户意图 | 工具 | Skill（规划） | 上下文 |
|----------|------|---------------|--------|
| 今天能不能做 / 情绪阶段 | `get_emotion_cycle` | vnpy-sentiment 扩展 | T-03 输出：阶段、仓位系数、允许模式 |
| 龙头 / 连板池 | `run_leader_screen` | vnpy-screening 扩展 | 雷达 leader 卡 + 硬过滤 |
| 短线观察组有哪些 | `get_short_term_watchlist` | vnpy-watchlist 扩展 | `watchlist_groups` |
| 帮我做次日计划 | `propose_trading_plan` | vnpy-trading（新） | 共振 + 选股 + 情绪 |
| 复盘今天交易 | `get_trade_journal` | vnpy-trading | `trade_journal` + 持仓 |
| 还能不能开仓 | `check_risk_gate` | vnpy-trading ✅ | 账户闸 + 情绪周期 |
| 这只能打板还是半路 | `evaluate_entry_mode` | vnpy-analysis | 标的 + T-03 + 连板地位 |

**页面 prompt 注入（规划）**：

| 页面 | 组装函数 | 新增字段 |
|------|----------|----------|
| 雷达 | `build_radar_ai_prompt` | `emotion_stage`, `max_position_pct` |
| 市场 | `build_market_ai_prompt`（待建） | 广度 + 连板高度摘要 |
| 自选持仓 | 持仓 AI | `exit_rules`, `off_plan` 提示 |

**约束（沿用）**：退潮期（`emotion_stage=retreat`）禁止给出激进追板建议；须引用 `SIGNAL_DISCLAIMER`。

## 通达信 MCP

- 配置：`mcp/mcp.json` → `mcpServers.tdx`
- 认证 Header：`tdx-api-key`
- 工具名格式：`mcp_tdx_<远端工具名>`

`diagnose_stock` 调用 `mcp_tdx_tdx_wenda_quotes`，查询行情、技术指标、财务、资金流。

## Python Skills

| Skill | 工具 |
|-------|------|
| vnpy-context | get_quote_context |
| vnpy-data | get_bars_summary, get_bars_data |
| vnpy-analysis | explain_screening_run, get_screening_context, technical_snapshot, list_strategy_signals, historical_pattern_summary, trend_scenario_summary |
| tdx-stock-diagnose | diagnose_stock |
| tdx-financial-analysis | analyze_financial |
| tdx-risk-analysis | analyze_risk |
| vnpy-backtest | list_strategies, get_backtest_result, list_backtest_history |
| vnpy-screening | list_screeners, list_recipes, run_recipe, propose_recipe, screen_by_condition, screen_by_pattern, propose_screening |
| vnpy-watchlist | get_watchlist, add_to_watchlist, remove_from_watchlist |
| vnpy-notes | get_stock_notes, append_stock_note_entry, update_stock_note_memo, delete_stock_note_entry, clear_stock_notes, list_stock_analysis_reports, get_stock_analysis_report |
| vnpy-sentiment | get_ashare_fear_greed_index（+ `get_emotion_cycle` 规划） |
| vnpy-trading | check_risk_gate ✅、compute_position_size ✅；propose_trading_plan、get_trade_journal（规划） |
| vnpy-screening | … + `run_leader_screen`（规划） |
| vnpy-watchlist | … + `get_short_term_watchlist` ✅ |

## 选股

| 路径 | 工具 | 条件 |
|------|------|------|
| 盘中/盘后多因子 | `run_recipe` | 高置信 preset/recipe（如 intraday_multi） |
| 多因子解析执行 | `propose_recipe` | 自定义配方或需先解析的多因子意图 |
| 自动 preset | `screen_by_condition` | 高置信内置 preset |
| 自动形态 | `screen_by_pattern` | 优先问小达 MCP；失败降级本地日 K / 行情 |
| 标杆对标 | `screen_reference_peer` | 以标杆股找同业同类（估值+动量） |
| 条件解析执行 | `propose_screening` | 已保存方案（`scheme_name`）、自定义阈值 |

内置 preset：涨幅榜、换手率排行、成交量放大、自定义筛选、低 PE、中大盘、主力净流入。`top_n` 1–200，默认 20。

执行：`runner.run_screener` → Redis 行情（交易时段）/ Tushare 回退 → `ScreeningService.persist_run_result` → `context_store` + `screener_runs`。

| 场景 | 行为 |
|------|------|
| Redis 无数据 | 返回 error，引导行情采集或打开市场页 |
| Tushare token 缺失 | 财务类 preset 报错 |
| 已保存方案 | 走 `propose_screening` 解析后自动执行 |

## 恐贪指数

工具：`get_ashare_fear_greed_index`（`vnpy-sentiment` Skill）。路由 enrichment 控制是否进入本轮 tool list；不注入页面上下文。

## 约束

- 不编造价格、指标
- 不给出具体买卖价位或确定性走势预测

## Skill 源码与 SKILL.md

Python 实现位于仓库根 `skills/`；完整清单见 **[skills/README.md](../skills/README.md)**。运行时由 `vnpy-skills` 加载，详细工具说明见各 `skills/<name>/SKILL.md`。

### 诊断 vs 团队分析

| 模式 | 工具 / 路径 | 适用 |
|------|-------------|------|
| 快速诊断 | `diagnose_stock`（问小达 MCP） | 单轮概览：行情 + 技术指标 + 财务 + 资金流 |
| 团队全面分析 | `team_analysis` → 并行子 Agent + chief | 分维度深挖；触发词或 `/team 600519` |

详见 [智能体投研团队](./team-agent.md)。
