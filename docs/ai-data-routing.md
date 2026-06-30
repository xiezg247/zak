# AI 数据路由

AI 助手各类问题对应的数据来源与工具。运行 `uv run python cli.py tools mcp-list` 可列出通达信 MCP 工具。

各功能域对**本地日 K** 的依赖见 [AI 功能与 K 线](./ai-kline-data.md)。

## 编排入口（AgentGateway）

对话经 `vnpy_llm.gateway.AgentGateway.send`：

1. **RoutingPlane** → 意图分类与 supervisor 委派 → `RoutingDecision`
2. **AgentRuntime** → `team_analysis` / `market` 专用编排，或 ReAct 工具循环 / 纯闲聊
3. **Handoff** → 诊断/回测/选股涉及大盘时串行追加 market Agent（`team_analysis` 不走 handoff）
4. **选股执行** → `propose_screening` / `propose_recipe` 默认弹 Qt 确认（`llm/nl_screening_confirm_enabled`）

`LlmEngine` 为 VeighNa 插件桥接；详见 [architecture.md §6](./architecture.md#6-ai)。  
LLM **不直接**调 `mcp_*`；综合诊断经 `diagnose_stock` Skill。

## 路由总表

| 用户意图 | 工具 | Skill | 降级 |
|----------|------|-------|------|
| 当前选中标的 | `get_quote_context` | vnpy-context | — |
| 本地 K 线 / 区间涨跌 | `get_bars_*` | vnpy-data | 提示下载日 K |
| 近期走势 / 历史统计 | `historical_pattern_summary` | vnpy-analysis | 不足 → 问小达 MCP |
| 技术面快照 | `technical_snapshot` | vnpy-analysis | 提示下载日 K |
| 快速综合诊断 | `diagnose_stock` | tdx-stock-diagnose | 问小达 MCP |
| 团队全面分析 | `team_analysis` | — | 预取不足自动深度；研报落笔记 |
| 财务深度 / 风险画像 | `analyze_financial` / `analyze_risk` | tdx-* | 缺失标 N/A |
| 实时行情 / 板块 | `mcp_tdx_*` | — | TickFlow / Redis |
| 财务 / 估值 / 宏观 | tushare-data | — | — |
| 选股结果解读 | `explain_screening_run` 等 | vnpy-analysis | 选股页方案 |
| 走势情景分析 | `trend_scenario_summary` | vnpy-analysis | K 不足提示下载 |
| 回测解读 | `get_backtest_result` 等 | vnpy-backtest | — |
| 情绪 / 择时 / 能不能做 | `get_emotion_cycle` | vnpy-sentiment | — |
| 恐贪指数 | `get_ashare_fear_greed_index` | vnpy-sentiment | enrichment 控制入列 |
| 雷达盘面 / 共振 | `get_radar_snapshot` | vnpy-radar | 须先刷新雷达页 |
| 龙头卡快照（只读） | `get_leader_pick_snapshot` | vnpy-radar | 不落库；`mainline` / `all_market` |
| 龙头 / 连板池 | `run_leader_screen` | vnpy-screening | 依赖雷达刷新 |
| 短线盘中上下文 | `get_short_term_watchlist` | vnpy-watchlist | — |
| 次日计划 | `propose_trading_plan` | vnpy-trading | 确认后写入 |
| 隔日卖点 | `evaluate_overnight_exit` | vnpy-trading | 持仓 + 行情 |
| 买点模式（打板/半路） | `evaluate_entry_mode` | vnpy-analysis | 单票 + 情绪阶段 |
| 龙头分层解读 | `explain_leader_tier` | vnpy-analysis | — |
| 监管异动距离 | `assess_regulatory_deviation` | vnpy-analysis | — |
| 复盘今天交易 | 笔记 + `build_positions_ai_prompt` | vnpy-notes | — |

**页面 prompt**：雷达 `build_radar_ai_prompt`、市场 `build_market_ai_prompt`、持仓 `build_positions_ai_prompt`。退潮期禁止激进追板；须引用 `SIGNAL_DISCLAIMER`。

## 通达信 MCP

配置：`mcp/mcp.json` → `mcpServers.tdx`；Header `tdx-api-key`；工具名 `mcp_tdx_<远端名>`。

## 选股执行

| 路径 | 工具 | 条件 |
|------|------|------|
| 多因子 | `run_recipe` / `propose_recipe` | preset/recipe 或需解析 |
| 条件 / 形态 | `screen_by_condition` / `screen_by_pattern` | preset 或 MCP→本地降级 |
| 标杆对标 | `screen_reference_peer` | 标杆股锚定 |
| 极致短线统一 | `ultra_short_unified` / `run_short_term_screen` | 含情绪 gate |
| 已保存方案 | `propose_screening` | 须用户确认 |

内置 preset：涨幅榜、换手、放量、低 PE、中大盘、主力净流入等。`top_n` 1–200，默认 20。  
执行链：Redis（交易时段）/ Tushare 回退 → `screener_runs` + `context_store`。

## Skill 清单

实现于 `skills/`；详见 [skills/README.md](../skills/README.md)。

| Skill | 主要工具 |
|-------|----------|
| vnpy-context / vnpy-data | 页面与 K 线 |
| vnpy-analysis | 技术面、情景、买点/龙头/监管评估 |
| vnpy-screening / vnpy-radar | 选股、雷达、龙头 |
| vnpy-watchlist / vnpy-notes / vnpy-trading | 自选、笔记、计划、隔日 |
| vnpy-backtest / vnpy-sentiment | 回测、情绪恐贪 |
| tdx-stock-diagnose / tdx-financial-analysis / tdx-risk-analysis | MCP 诊断与团队子 Agent |

**诊断 vs 团队**：`diagnose_stock` 单轮概览；`team_analysis` 分维度深挖（`/team`）。见 [智能体投研团队](./team-agent.md)。

## 约束

不编造价格/指标；不给出具体买卖价或确定性走势预测。

## 快捷指令（Ctrl+L 面板）

实现于 `vnpy_ashare/ai/context/`（`enrichment.py` 路由 + 各页 `build_*_quick_actions`）。悬浮球与全屏助手共用 `QuickAction` 模型；**全屏助手**对 `auto_send=True` 的项点击后直接发送，**悬浮/紧凑面板**仅预填。

### 个股（有选中时，3 个顶层）

| 顶层 | 内容 |
|------|------|
| 快速研判 | 综合诊断 / 财务 / 资金流 / 团队全面分析 |
| 技术与走势 | 技术·均线量比 … 走势·近 N 日 … 预测·情景 |
| 对标与操作 | 找同类 Top 10/20/30 + 页面操作（板块概览、持仓策略等） |

### 页面级（无选中或叠加）

| 页面 | 主要 chip |
|------|-----------|
| 守则 | 今日一句纪律 · 对照今日计划 · 持仓纪律检查 |
| 自选（无选中） | 持仓复盘 · 今日短线环境 ·（可选）解读选股结果 |
| 市场 | 大盘环境 · 今日短线环境（+ 个股菜单） |
| 雷达 | 今日洞察 · 共振解读 …（有选中时保留「今日洞察」+ 个股菜单） |
| 选股 | 解读结果 · 雷达龙头 · 共振解读 · 形态选股 · 条件选股 |
| 板块资金 | 资金结构 · 板块轮动 · 雷达龙头 |
| 策略回测 / 回测对比 | 解读回测/批次 · 参数或归因建议 |
| 信息流 / 数据管理 | 见各页 `build_*_page_quick_actions` |

### 条件选股子项（展示名 = 配方/preset）

盘中多因子 · 盘后多因子 · 低 PE · 主力净流入 · 成交量放大。口语「短线游资」「成长赛道」等仍可由 `router.py` 关键词映射。

### auto_send 策略

| 类型 | auto_send | 示例 |
|------|-----------|------|
| 环境/解读类 | 是（仅全屏助手生效） | 大盘环境、解读选股结果、雷达洞察 |
| 执行/重任务类 | 否（预填后确认） | 团队全面分析、形态/条件选股、走势预测 |

悬浮面板超过 5 个 chip 时，余量收入 **「更多」** 菜单（`vnpy_llm/ui/floating/widgets.py`）。
