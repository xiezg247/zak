# AI 数据路由

AI 助手各类问题对应的数据来源与工具。运行 `uv run python cli.py tools mcp-list` 可列出通达信 MCP 工具。

各功能域对**本地日 K** 的依赖程度、下载范围建议见 [AI 功能与 K 线](./ai-kline-data.md)。

## LangGraph 编排（有工具路径）

有工具对话统一走 `vnpy_llm.graph.runner.stream_with_tools`：

1. **意图路由**（`routing/router.py`）→ 工具子集 + `routing_hint`
2. **Supervisor**（`graph/supervisor.py`）→ 委派 Specialist Agent（market / research / screening / backtest / data / general）
3. **ReAct loop**（`langchain.agents.create_agent`）→ Skill / MCP 工具执行
4. **Handoff**（`graph/handoff.py`）→ 诊断/回测/选股若涉及大盘或技术面，串行追加 market Agent；段间以 `**市场环境**` 等标题分隔
5. **选股执行** → `propose_screening` / `propose_recipe` 解析后由 Skill 直接执行（无弹窗确认）

无工具闲聊仍走 `chat/client.stream_chat_completion`，system prompt 见 `routing/prompts.py`（与 `routing/base_prompt.py` 共用基座）。

LLM **不直接调用** `mcp_*`；综合诊断经 `diagnose_stock` Skill 访问通达信 MCP。

## 路由总表

| 用户意图 | 工具 / 数据源 | 降级 |
|----------|---------------|------|
| 当前选中标的 | `get_quote_context` | — |
| 本地 K 线 / 区间涨跌 | `get_bars_summary` / `get_bars_data` | 提示下载日 K |
| 近期走势 / 历史统计 | `historical_pattern_summary` | 本地不足时问小达 MCP 兜底 |
| 技术面快照 | `technical_snapshot` | 提示下载日 K |
| 综合诊断 | `diagnose_stock` | — |
| 实时行情 / 板块 | 通达信 MCP `mcp_tdx_*` | TickFlow / Redis |
| 财务 / 估值 / 宏观 | `tushare-data` Skill | — |
| 选股结果解读 | `explain_screening_run` / `get_screening_context` | 选股页运行方案 |
| 走势预测 / 情景分析 | `trend_scenario_summary` + `mcp_tdx_tdx_wenda_quotes` | 本地 K 不足时提示下载日 K |
| 回测解读 | `get_backtest_result` / `list_backtest_history` | — |

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
| vnpy-backtest | list_strategies, get_backtest_result, list_backtest_history |
| vnpy-screening | list_screeners, list_recipes, run_recipe, propose_recipe, screen_by_condition, screen_by_pattern, propose_screening |
| vnpy-watchlist | get_watchlist, add_to_watchlist, remove_from_watchlist |
| vnpy-sentiment | get_ashare_fear_greed_index |

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
