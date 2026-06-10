# 架构说明

## 主窗口

zak 继承 `vnpy.trader.ui.MainWindow`：

- 复用 MainEngine、EventEngine、App 插件
- 禁用 vnpy 默认 `init_dock()`
- 中央区域为左侧导航 + StackedWidget
- 嵌入 vnpy 策略回测、数据管理 Widget

数据模型：`StockItem`、`QuoteSnapshot`（非 vnpy `TickData` / `ContractData`）。

## GUI 布局

```
┌─────────────────────────────────────────────────────────┐
│ 菜单栏：系统 / 工具 / 配置 / 帮助                        │
├────┬──────────────────────────────────────────┬─────────┤
│左侧│  中央内容区（StackedWidget）                │ AI Dock │
│导航│  自选/市场/策略选股/自动选股/本地/回测/…     │（可选）  │
└────┴──────────────────────────────────────────┴─────────┘
```

导航：`vnpy_ashare/ui/nav.py` → `APP_NAV_ENTRIES`。

## 包结构

| 包 | 职责 |
|----|------|
| `packages/vnpy-ashare/vnpy_ashare/app/` | 启动、引擎、事件 |
| `packages/vnpy-ashare/vnpy_ashare/config/` | 常量、schema、.env 桥接 |
| `packages/vnpy-ashare/vnpy_ashare/domain/` | models、calendar、market_hours |
| `packages/vnpy-ashare/vnpy_ashare/data/` | K 线下载、bar_store、健康检测 |
| `packages/vnpy-ashare/vnpy_ashare/storage/` | app_db、universe、交易日历 |
| `packages/vnpy-ashare/vnpy_ashare/backtest/` | CTA App/Engine、run_store |
| `packages/vnpy-ashare/vnpy_ashare/services/` | Quote、Bar、Backtest、Screening、Watchlist、Analysis、Sentiment |
| `packages/vnpy-ashare/vnpy_ashare/screener/` | 因子、规则、方案、配方、标杆对标、NL 解析 |
| `packages/vnpy-ashare/vnpy_ashare/scheduler/` + `jobs/` | 定时任务 |
| `packages/vnpy-ashare/vnpy_ashare/ui/shell/` | 主窗口、导航、设置、数据管理 |
| `packages/vnpy-ashare/vnpy_ashare/ui/quotes/` | 看盘页（QuotesPage + controller + 图表） |
| `packages/vnpy-ashare/vnpy_ashare/ui/screener/` | 选股页 |
| `packages/vnpy-ashare/vnpy_ashare/ui/backtest/` | 回测页 |
| `packages/vnpy-ashare/vnpy_ashare/ui/components/` | 跨页复用（chart_style、表格、任务输出） |
| `packages/vnpy-tickflow` | TickFlow 适配 |
| `packages/vnpy-llm` | LLM 对话（`app/`、`chat/`、`routing/`、`tools/`、`trace/`、`ui/`） |
| `packages/vnpy-skills` | Agent Skill 引擎 |
| `packages/vnpy-mcp` | MCP 远端工具（`mcp/mcp.json`） |
| `packages/vnpy-common` | 路径、AI 协议、终端主题 |
| `packages/vnpy-ashare/vnpy_ashare/ai` | `context_store`、全屏页 |

## 配置

`.env` 为密钥真源；`vt_setting.json` 为 VeighNa 运行时配置。

`config_schema` → `config_bridge` → `vt_settings`；GUI 编辑在 `ui/settings_dialog.py`。

## 看盘页（`ui/quotes/`）

`QuotesPage` 组合各 controller：

| 模块 | 职责 |
|------|------|
| `page_shell.py` | 布局 |
| `data_loader_controller.py` | 列表、市场榜、universe |
| `table_controller.py` | 表格与选中 |
| `actions_controller.py` | 诊断、AI、回测、标杆对标 |
| `local_data_controller.py` | 本地 K 线 meta、下载、缺口 |
| `quote_stream_controller.py` | TickFlow WebSocket |
| `watchlist_controller.py` | 自选 CRUD |
| `batch_backtest_controller.py` | 批量回测 |

批量回测：`batch_backtest_flow.py`；对比页：`batch_backtest_page.py`。

## 行情 Provider

看盘 UI 只依赖 `QuoteSnapshot`（`quotes/provider.py`）：

| Provider | 用途 |
|----------|------|
| `TickflowQuoteProvider` | 自选页直连 |
| `RedisQuoteProvider` | 市场页涨幅榜 |

```
QuotesPage → QuoteProvider
              ├── TickflowQuoteProvider
              └── RedisQuoteProvider
```

数据流：TickFlow → 自选页；Redis → 市场页；K 线数据根据 `DATABASE_NAME` 写入 SQLite 或 PostgreSQL。

## AI 助手

| 模式 | 入口 |
|------|------|
| 悬浮球 | 自选/市场/本地/策略选股/自动选股；`Ctrl+L` / `⌘L` |
| Dock | 右侧可停靠 |
| 全屏 | 导航「AI 助手」 |

Service 写入 `context_store`（线程安全内存）：

| Service | 写入内容 |
|---------|----------|
| `QuoteService` | 页面上下文、行情缓存 |
| `ScreeningService` | 选股结果 |
| `BacktestService` | 回测摘要 |
| `AnalysisService` | 诊断结果 |
| `BarService` | 数据管理页上下文 |
| `SentimentService` | 恐贪指数 |

UI / Worker 经 Service 写上下文；Skills / LLM 只读。Agent Skill（`SKILL.md`）在 System Prompt 中仅注入名称与简介，详细说明通过 `read_skill_file` 按需加载。

### 悬浮球

协调层：`ui/floating_controller.py`（`FloatingAiController`）。

| 项 | 说明 |
|----|------|
| 白名单页 | 自选、市场、本地、策略选股、自动选股 |
| 快捷键 | `Ctrl+L` / `⌘L` 切换显隐 |
| ContextChip | 当前页、选中标的、选股结果数 |
| Quick Actions | 按页的 chips / 右键菜单 |
| 非白名单页 | `EVENT_ASK_AI` 跳转自选页再开球 |

## 本地 K 线健康

`bar_health.py` + `local_data_controller.py` + `jobs/local_fill.py`。

| 状态 | 含义 |
|------|------|
| OK | 覆盖最近交易日 |
| STALE | 结束日期早于最近交易日 |
| GAPS | 选中后扫描到内部断层 |
| UNKNOWN | 无本地数据 |

列表页判 OK/STALE/UNKNOWN；GAPS 由选中行的 `BarGapCheckWorker` 异步扫描。交易日历：Tushare → `trade_calendar` 表（`calendar.py`）。
