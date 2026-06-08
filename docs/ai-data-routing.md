# AI 数据路由说明

本文档说明 AI 助手各类问题应使用的数据来源与工具。运行 `python scripts/list_mcp_tools.py` 可刷新通达信 MCP 工具清单。

## 路由总表

| 用户意图 | 优先工具 / 数据源 | 降级 |
|----------|-------------------|------|
| 当前选中标的 | `get_quote_context` | — |
| 本地 K 线 / 区间涨跌 | `get_bars_summary` / `get_bars_data` | 提示下载日 K |
| 技术面快照 | `technical_snapshot` / `diagnose_stock` | 同上 |
| 综合诊断 | `diagnose_stock` | — |
| 券商研报 / 评级 | `diagnose_stock`（内调通达信 MCP）或 `mcp_tdx_*` | Tushare `research_report`（TDX 不可用时） |
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

### 研报类工具

`AnalysisService` 会自动匹配名称含以下关键词的 MCP 工具：

- `report` / `research` / `研报` / `rating`
- 若无研报工具，尝试 `f10` / `fundamental` / `financial`

## Python Skills

| Skill | 工具 |
|-------|------|
| vnpy-context | get_quote_context |
| vnpy-data | get_bars_summary, get_bars_data |
| vnpy-analysis | diagnose_stock, technical_snapshot |
| vnpy-backtest | list_strategies, get_backtest_result, list_backtest_history |
| vnpy-screening | list_screeners, screen_by_condition |
| vnpy-watchlist | get_watchlist, add_to_watchlist, remove_from_watchlist |

## 合规

- 禁止编造价格、指标、研报观点
- 禁止具体买卖价位与确定性走势预测
- 研报引用须注明来源（通达信 MCP）与日期
