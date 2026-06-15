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
│导航│  自选/市场/板块资金/雷达/本地/选股/回测/…     │（可选）  │
└────┴──────────────────────────────────────────┴─────────┘
```

导航：`vnpy_ashare/ui/shell/nav.py` → `APP_NAV_GROUPS`（侧栏）+ `BACKSTAGE_ENTRIES`（菜单栏后台页）。

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
| `packages/vnpy-ashare/vnpy_ashare/quotes/` | 行情领域：快照、Provider、排行、市场概览、雷达数据加载（见下节） |
| `packages/vnpy-ashare/vnpy_ashare/screener/` | 因子、规则、方案、配方（`run/`、`recipe/`、`preset/`、`sector/`、`data/`、`dimensions/`） |
| `packages/vnpy-ashare/vnpy_ashare/scheduler/` + `jobs/` | 定时任务 |
| `packages/vnpy-ashare/vnpy_ashare/ui/shell/` | 主窗口、导航（`settings/`、`manager/`） |
| `packages/vnpy-ashare/vnpy_ashare/ui/quotes/` | 看盘页 + 雷达（`page/`、`radar/`、`chart/`、`table/`、`panels/`、`workers/`） |
| `packages/vnpy-ashare/vnpy_ashare/ui/sector_flow/` | 板块资金页 |
| `packages/vnpy-ashare/vnpy_ashare/ui/screener/` | 选股 hub（`pages/screener_hub_page.py`：条件选股 + 多因子配方；`widgets/`、`dialogs/`、`workers/`） |
| `packages/vnpy-ashare/vnpy_ashare/ui/backtest/` | 回测页（`pages/`、`flow/`、`chart/`、`table/`） |
| `packages/vnpy-ashare/vnpy_ashare/ui/components/` | 跨页复用（chart_style、表格、任务输出） |
| `packages/vnpy-tickflow` | TickFlow 适配（`client/`、`klines/`、`mapping/`、`datafeed/`） |
| `packages/vnpy-llm` | LLM 对话（`gateway/` 控制面、`app/`、`chat/`、`routing/`、`graph/`、`tools/`、`trace/`、`ui/`） |
| `packages/vnpy-skills` | Agent Skill 引擎（`app/`、`domain/`、`agent/`） |
| `packages/vnpy-mcp` | MCP 远端工具（`app/`、`config/`、`domain/`、`remote/`） |
| `packages/vnpy-common` | 路径、AI 协议、终端主题 |
| `packages/vnpy-ashare/vnpy_ashare/ai` | `context/`（store、组装）、`ui/`（全屏页） |

## 配置

`.env` 为密钥真源；`vt_setting.json` 为 VeighNa 运行时配置。

`config_schema` → `config_bridge` → `vt_settings` → `config/apply`（分级热应用）；GUI 编辑在 `ui/shell/settings/`。详见 [配置分级热加载](./config-hot-reload.md)。

## 行情领域（`quotes/`）

领域逻辑按子域拆分子包；包内与 UI 均从子包或 `quotes/__init__.py` 公开 API 导入。

```text
quotes/
├── __init__.py  公开 API（QuoteSnapshot、Provider 等）
├── core/        snapshot、provider、redis_store、depth_snapshot、enrich
├── rank/        rank_catalog、rank_engine、rank_scope
├── market/      market_breadth、market_environment、market_overview_loaders、moneyflow_kind
├── misc/        position_anomaly、speed_baseline
└── radar/       radar_*（catalog、loaders、models、horizon、resonance 等）
```

| 子包 | 职责 |
|------|------|
| `core/` | `QuoteSnapshot`、TickFlow/Redis Provider、Redis 缓存、盘口深度、行情 enrich |
| `rank/` | 涨幅/成交额等排行定义与取值 |
| `market/` | 市场宽度、北向/环境快照、概览 loader |
| `misc/` | 持仓异动、涨速基线等辅助指标 |
| `radar/` | 雷达卡片 catalog、数据加载、共振、horizon 扫描 |

## 看盘页（`ui/quotes/`）

`QuotesPage` 组合各子包：

| 子包 | 职责 |
|------|------|
| `page/` | QuotesPage、布局 shell、配置、运行输出 |
| `controllers/` | 表格、数据加载、操作、自选、分页 |
| `table/` | 列定义、Model、市场展示 |
| `chart/` | ChartPanel、日 K / 分时 / 分 K |
| `panels/` | 盘口、诊断、loading |
| `watchlist_signals/` | 自选策略信号区 |
| `workers/` | K 线 / 行情后台 Worker |

批量回测：`ui/backtest/flow/`；对比页：`ui/backtest/pages/`。

## 板块资金与雷达

| 页 | 路径 | 职责 |
|----|------|------|
| 板块资金 | `ui/sector_flow/` | 行业/概念资金流向；`SectorFlowService` 聚合 Tushare 板块数据 |
| 雷达 | `ui/quotes/radar/` + `page_shell.RadarPageWidget` | 多卡片盘面扫描、共振列表；卡片可跳转板块资金 / 条件选股 |

## 选股 Hub（`ui/screener/`）

`ScreenerHubPageWidget` 内嵌「条件选股」（`screener_page.py`）与「多因子配方」（`auto_screener_page.py`）两个 Tab，共用运行历史侧栏与 `ScreenerResultInsights`（diff 文本 + `SectorDistributionPanel`）。

## 行情 Provider

看盘 UI 只依赖 `QuoteSnapshot`（`quotes/core/provider.py`）：

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
| 悬浮球 | 自选/市场/板块资金/雷达/本地/选股；`Ctrl+L` / `⌘L` |
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

### AgentGateway 控制面

编排入口为 `vnpy_llm.gateway.AgentGateway`；`LlmEngine` 仅作 VeighNa 插件壳与 Qt 信号桥接。

```
UI（悬浮球 / Dock / 全屏）
        ↓ send / subscribe
LlmEngine（Qt 信号桥接）
        ↓
AgentGateway
├── SessionManager      # 会话 CRUD、floating/assistant 双轨
├── TraceCoordinator    # Turn Trace（路由 / 工具 / handoff / 回复）
├── ToolRegistry        # Skill + MCP 注册与执行
├── ContextAssembler    # 终端上下文与 System Prompt 拼装
├── RoutingPlane        # router + supervisor 一层对外
└── AgentRuntime        # 有工具 / 无工具统一流式入口
        ↓
graph/runner.stream_with_tools  或  chat/client.stream_chat_completion
```

| API | 说明 |
|-----|------|
| `send(SendRequest)` | 单轮流式回复；yield 文本 delta |
| `subscribe(listener)` | 订阅 `AgentEvent`（chat / session / tool / trace） |
| `cancel()` | 中断当前流式生成 |

有工具路径的数据路由与工具表见 [ai-data-routing.md](./ai-data-routing.md)。

### 悬浮球

协调层：`ui/floating_controller.py`（`FloatingAiController`）。

| 项 | 说明 |
|----|------|
| 白名单页 | 自选、市场、板块资金、雷达、本地、选股 |
| 快捷键 | `Ctrl+L` / `⌘L` 切换显隐 |
| ContextChip | 当前页、选中标的、选股结果数 |
| Quick Actions | 按页的 chips / 右键菜单 |
| 非白名单页 / 用户已隐藏悬浮球 | `EVENT_ASK_AI` 跳转全屏 AI 助手 |

## 本地 K 线健康

`bar_health.py` + `local_data_controller.py` + `jobs/local_fill.py`。

| 状态 | 含义 |
|------|------|
| OK | 覆盖最近交易日 |
| STALE | 结束日期早于最近交易日 |
| GAPS | 选中后扫描到内部断层 |
| UNKNOWN | 无本地数据 |

列表页判 OK/STALE/UNKNOWN；GAPS 由选中行的 `BarGapCheckWorker` 异步扫描。交易日历：Tushare → `trade_calendar` 表（`calendar.py`）。
