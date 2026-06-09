# AI 数据路由说明

本文档说明 AI 助手各类问题应使用的数据来源与工具。运行 `python scripts/list_mcp_tools.py` 可刷新通达信 MCP 工具清单。

## 路由总表

| 用户意图 | 优先工具 / 数据源 | 降级 |
|----------|-------------------|------|
| 当前选中标的 | `get_quote_context` | — |
| 本地 K 线 / 区间涨跌 | `get_bars_summary` / `get_bars_data` | 提示下载日 K |
| 技术面快照 | `technical_snapshot`（本地 K 线） | 同上 |
| 综合诊断 | `diagnose_stock`（tdx-stock-diagnose，问小达 MCP） | — |
| 券商研报 / 评级 | `diagnose_stock` 或 `mcp_tdx_tdx_wenda_quotes` | — |
| 实时行情 / 板块 / F10 | 通达信 MCP `mcp_tdx_*` | TickFlow / Redis |
| 财务 / 估值 / 宏观 | `tushare-data` Skill（`run_python`） | — |
| 选股结果解读 | `get_screening_context` | 选股页运行方案 |
| 回测解读 | `get_backtest_result` / `list_backtest_history` | — |

## 通达信 MCP

- 配置：`mcp/mcp.json` → `mcpServers.tdx`
- 认证 Header：`tdx-api-key`
- LLM 工具名格式：`mcp_tdx_<远端工具名>`
- 已知示例（以 `list_mcp_tools.py` 输出为准）：
  - `mcp_tdx_stock_quotes` — 个股报价

### 问小达工具（个股诊断）

`diagnose_stock`（tdx-stock-diagnose Skill）自动调用 `mcp_tdx_tdx_wenda_quotes`，按维度查询：

- 行情：现价、涨跌幅、成交量
- 技术指标：MACD、KDJ、RSI
- 财务：PE、ROE
- 资金流：主力净额
- 研报评级（可选）

不再依赖本地 K 线。旧版研报/F10 自动匹配逻辑仍保留在 `AnalysisService._fetch_reports`，供其他路径使用。

## Python Skills

| Skill | 工具 |
|-------|------|
| vnpy-context | get_quote_context |
| vnpy-data | get_bars_summary, get_bars_data |
| vnpy-analysis | technical_snapshot, list_strategy_signals, historical_pattern_summary |
| tdx-stock-diagnose | diagnose_stock |
| vnpy-backtest | list_strategies, get_backtest_result, list_backtest_history |
| vnpy-screening | list_screeners, screen_by_condition |
| vnpy-watchlist | get_watchlist, add_to_watchlist, remove_from_watchlist |
| vnpy-sentiment | get_ashare_fear_greed_index（需 TUSHARE_TOKEN） |

## 恐贪指数（AI 自主运用）

- 工具：`get_ashare_fear_greed_index`（`vnpy-sentiment` Skill）
- 路由 enrichment：`skip` / `consider` / `highlight` 三档，控制工具是否进入本轮 tool list
- **不**注入页面上下文；由主对话自行判断是否调用与是否写入正文
- 典型触发：大盘环境、市场节奏、综合研判、选股背景；**不**用于纯价格/自选 CRUD/回测数值

## 合规

- 禁止编造价格、指标、研报观点
- 禁止具体买卖价位与确定性走势预测
- 研报引用须注明来源（通达信 MCP）与日期
