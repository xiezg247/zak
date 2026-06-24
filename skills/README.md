# Skills 目录

Agent 可调用的业务 Skill：Python 实现（`*.py`）+ 可选 `SKILL.md`（供 `read_skill_file` 按需加载）。

## 带 SKILL.md 的包

| 目录 | 工具 | 说明 | 文档 |
|------|------|------|------|
| `tdx-stock-diagnose/` | `diagnose_stock` | 问小达 MCP 快速综合诊断 | [SKILL.md](./tdx-stock-diagnose/SKILL.md) |
| `tdx-financial-analysis/` | `analyze_financial` | 财务深度（团队 financial Agent） | [SKILL.md](./tdx-financial-analysis/SKILL.md) |
| `tdx-risk-analysis/` | `analyze_risk` | 风险画像（团队 risk Agent） | [SKILL.md](./tdx-risk-analysis/SKILL.md) |
| `tdx-stock-picker/` | — | 选股意图 → 终端工具路由说明 | [SKILL.md](./tdx-stock-picker/SKILL.md) |
| `tushare-data/` | Tushare 脚本 | 财务 / 宏观 / 板块研究 | [SKILL.md](./tushare-data/SKILL.md) |
| `tickflow/` | TickFlow SDK | 行情 / K 线（外部 Agent 用） | [SKILL.md](./tickflow/SKILL.md) |

## Python 实现（根目录 `*.py`）

由 `skills/registry.py` 注册，运行时加载自 `vnpy-skills`：

| 文件 | skill_name | 主要工具 |
|------|------------|----------|
| `vnpy_context_skill.py` | vnpy-context | get_quote_context |
| `vnpy_data_skill.py` | vnpy-data | get_bars_summary, get_bars_data |
| `vnpy_analysis_skill.py` | vnpy-analysis | technical_snapshot、evaluate_entry_mode、explain_screening_run、… |
| `vnpy_screening_skill.py` | vnpy-screening | run_recipe, screen_by_condition, … |
| `vnpy_radar_skill.py` | vnpy-radar | get_radar_snapshot, run_short_term_screen（ultra_short_unified）, run_leader_screen, … |
| `vnpy_backtest_skill.py` | vnpy-backtest | get_backtest_result, … |
| `vnpy_watchlist_skill.py` | vnpy-watchlist | get_watchlist、get_short_term_watchlist、add_to_watchlist、… |
| `vnpy_notes_skill.py` | vnpy-notes | get_stock_notes, … |
| `vnpy_feed_skill.py` | vnpy-feed | list_feed_subscriptions、get_feed_items、check_bilibili_updated_today |
| `vnpy_sentiment_skill.py` | vnpy-sentiment | get_ashare_fear_greed_index、get_emotion_cycle |
| `vnpy_trading_skill.py` | vnpy-trading | get_trading_plan、propose_trading_plan、evaluate_overnight_exit |
| `tdx_diagnose_skill.py` | tdx-stock-diagnose | diagnose_stock |
| `financial_analysis_skill.py` | tdx-financial-analysis | analyze_financial |
| `risk_analysis_skill.py` | tdx-risk-analysis | analyze_risk |

同步到运行环境：`uv run python cli.py skills sync`

## 相关文档

- [AI 数据路由](../docs/ai-data-routing.md)
- [AI 功能与 K 线](../docs/ai-kline-data.md)
- [智能体投研团队](../docs/team-agent.md)
- [选股 Hub 使用指南](../docs/screener-hub-guide.md)
- [文档索引](../docs/README.md)
