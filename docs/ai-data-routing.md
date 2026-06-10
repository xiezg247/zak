# AI 数据路由

AI 助手各类问题对应的数据来源与工具。运行 `uv run python scripts/list_mcp_tools.py` 可列出通达信 MCP 工具。

## 路由总表

| 用户意图 | 工具 / 数据源 | 降级 |
|----------|---------------|------|
| 当前选中标的 | `get_quote_context` | — |
| 本地 K 线 / 区间涨跌 | `get_bars_summary` / `get_bars_data` | 提示下载日 K |
| 技术面快照 | `technical_snapshot` | 提示下载日 K |
| 综合诊断 | `diagnose_stock` | — |
| 券商研报 / 评级 | `diagnose_stock` 或 `mcp_tdx_tdx_wenda_quotes` | — |
| 实时行情 / 板块 / F10 | 通达信 MCP `mcp_tdx_*` | TickFlow / Redis |
| 财务 / 估值 / 宏观 | `tushare-data` Skill | — |
| 选股结果解读 | `explain_screening_run` / `get_screening_context` | 选股页运行方案 |
| 回测解读 | `get_backtest_result` / `list_backtest_history` | — |

## 通达信 MCP

- 配置：`mcp/mcp.json` → `mcpServers.tdx`
- 认证 Header：`tdx-api-key`
- 工具名格式：`mcp_tdx_<远端工具名>`

`diagnose_stock` 调用 `mcp_tdx_tdx_wenda_quotes`，查询行情、技术指标、财务、资金流、研报评级。

## Python Skills

| Skill | 工具 |
|-------|------|
| vnpy-context | get_quote_context |
| vnpy-data | get_bars_summary, get_bars_data |
| vnpy-analysis | explain_screening_run, get_screening_context, technical_snapshot, list_strategy_signals, historical_pattern_summary |
| tdx-stock-diagnose | diagnose_stock |
| vnpy-backtest | list_strategies, get_backtest_result, list_backtest_history |
| vnpy-screening | list_screeners, list_recipes, run_recipe, propose_recipe, screen_by_condition, screen_by_pattern, propose_screening |
| vnpy-watchlist | get_watchlist, add_to_watchlist, remove_from_watchlist |
| vnpy-sentiment | get_ashare_fear_greed_index |

## 选股

| 路径 | 工具 | 条件 |
|------|------|------|
| 盘中/盘后多因子 | `run_recipe` | 意图明确（如 intraday_multi） |
| 多因子草案 | `propose_recipe` | 自定义配方、意图待确认 |
| 自动 preset | `screen_by_condition` | 内置 preset |
| 自动形态 | `screen_by_pattern` | 老鸭头/均线多头/W底/主题投资 |
| 确认 | `propose_screening` | 已保存方案、单一条件复杂 |

内置 preset：涨幅榜、换手率排行、成交量放大、自定义筛选、低 PE、中大盘、主力净流入。`top_n` 1–200，默认 20。

执行：`runner.run_screener` → Redis 行情（交易时段）/ Tushare 回退 → `ScreeningService.persist_run_result` → `context_store` + `screener_runs`。

| 场景 | 行为 |
|------|------|
| Redis 无数据 | 返回 error，引导行情采集或打开市场页 |
| Tushare token 缺失 | 财务类 preset 报错 |
| 已保存方案 | 走 `propose_screening` 确认 |

## 恐贪指数

工具：`get_ashare_fear_greed_index`（`vnpy-sentiment` Skill）。路由 enrichment 控制是否进入本轮 tool list；不注入页面上下文。

## 约束

- 不编造价格、指标、研报观点
- 不给出具体买卖价位或确定性走势预测
- 研报引用注明来源与日期
