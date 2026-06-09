# 架构说明

## 与 vnpy 默认 Trader 的关系

`vnpy_zak` **继承** `vnpy.trader.ui.MainWindow`，但**不采用**默认的期货实盘交易布局。

```
vnpy MainWindow（基类）
├── 复用：MainEngine / EventEngine、App 插件注册、部分菜单、窗口配置
├── 禁用：init_dock() 默认交易 Dock（下单/委托/持仓/资金/TickMonitor）
├── 替换：中央区域 → 自建左侧导航 + StackedWidget
└── 嵌入：策略回测 / 数据管理（vnpy 官方 Widget）
```

| 维度 | vnpy 默认 Trader | vnpy_zak 自建看盘 |
|------|------------------|-------------------|
| 定位 | 通用实盘交易终端（含期货） | A 股看盘 + 回测 + **策略实盘（规划）** |
| 布局 | 多 Dock 环绕 | 单页行情终端（列表 + K 线 + 五档） |
| 行情 | Gateway → OMS → TickMonitor | TickFlow / Redis（未来可切换为 Gateway 优先） |
| 数据模型 | `TickData` / `ContractData` | `StockItem` / `QuoteSnapshot` |
| 交易 | TradingWidget 下单 | 当前未接 Gateway；规划 A 股现货实盘 |
| 策略实盘 | CTA策略 + Gateway | 规划：`AShareTemplate` 与回测同策略类；CTA策略页暂未挂载 |

**结论**：看盘 UI 自建；vnpy 提供 CTA 回测/实盘引擎与 Gateway 交易能力。远期以 **A 股 Gateway + PaperAccount + CTA策略页** 跑现货自动交易，**不用**期货 CTP。

## 当前 GUI 分层

```
┌─────────────────────────────────────────────────────────┐
│ 菜单栏：系统 / 工具 / 配置 / 帮助                        │
├────┬──────────────────────────────────────────┬─────────┤
│左侧│  中央内容区（StackedWidget）                │ AI Dock │
│导航│  · 自选 / 市场 / 本地（看盘三页）          │（可选）  │
│    │  · 策略回测 / 数据管理                    │         │
└────┴──────────────────────────────────────────┴─────────┘
```

### 包职责

| 包 | 职责 |
|----|------|
| `vnpy_ashare` | A 股行情页、主窗口、调度、元数据、AI 全屏页 |
| `vnpy_ashare/services/` | **Service 业务层**（6 个 Service）：K 线查询、行情上下文、回测管理、选股、自选 CRUD、技术分析 |
| `vnpy_ashare/screener/` | **选股模块**（13 文件）：因子封装、规则引擎、方案持久化、Tushare 接入、NL 解析 |
| `vnpy_ashare/backtest/` | 回测结果落地（`run_store.py`） |
| `vnpy_ashare/scheduler/` | 定时任务调度管理 |
| `vnpy_ashare/jobs/` | 任务定义（下载/行情/同步） |
| `vnpy_tickflow` | TickFlow 行情适配器 |
| `vnpy_llm` | 通用 LLM 对话（client / engine / panel） |
| `vnpy_skills` | Agent Skill 引擎（工具注册、执行、系统提示词注入） |
| `vnpy_mcp` | MCP 远端工具集成（从 `mcp/mcp.json` 发现工具） |
| `vnpy_ashare/ai` | A 股 AI 上下文（`context.py`、`context_store.py`）、全屏页 |

### 配置单源（`.env` ↔ `vt_setting.json`）

| 模块 | 职责 |
|------|------|
| `config_schema.py` | 可配置项定义（ENV / VT 字段 spec） |
| `config_bridge.py` | ENV→VT 构建、`detect_config_drift()` 漂移检测 |
| `vt_settings.py` | 运行时读写、`sync_vt_settings_from_env()` |
| `ui/settings_snapshot.py` | 配置页数据解析与来源标记 |
| `ui/settings_dialog.py` | GUI 编辑 + 漂移提示 +「从 .env 同步」 |

`.env` 为密钥与部署环境真源；`vt_setting.json` 为 VeighNa 运行时配置。`scripts/init_config.py` 与设置页「从 .env 同步」均调用 `build_vt_settings()` → `config_bridge`。

### 看盘页 UI 拆分（`ui/quotes/`）

`QuotesPage`（`ui/quotes_page.py`）作为薄壳组合各 controller，子包 `ui/quotes/` 按职责拆分：

| 模块 | 职责 |
|------|------|
| `page_shell.py` | 工具栏、表格、报价头、K 线/五档/诊断区布局 |
| `data_loader_controller.py` | 列表加载、市场榜分页数据、universe 同步 |
| `table_controller.py` | 列配置、表格渲染、筛选、选中 |
| `actions_controller.py` | 诊断、AI 问句、回测、右键菜单、行情刷新 |
| `local_data_controller.py` | 本地 K 线 meta、下载、缺口检查、K 线加载 |
| `quote_stream_controller.py` | TickFlow WebSocket 流 |
| `pagination_controller.py` | 市场榜分页导航 |
| `watchlist_controller.py` | 自选 CRUD |
| `workers/quotes_workers.py` | 后台 Worker（行情/下载/加载等） |

`ui/worker.py` 保留为 re-export 兼容层，旧 import 路径仍可用。

### 行情 Provider 抽象

看盘 UI（`QuotesPage`）只依赖 `QuoteSnapshot`，不绑定具体数据源。`vnpy_ashare/quotes/provider.py` 已定义：

| Provider | 现状 | 角色 |
|----------|------|------|
| `TickflowQuoteProvider` | 自选页直连 / REST | 研究主源 |
| `RedisQuoteProvider` | 市场页涨幅榜 | 批量快照 |
| `GatewayQuoteProvider` | **未实现** | 实盘主源（规划） |

```
QuotesPage / Workers
        ↓
   QuoteProvider（接口）
        ├── GatewayQuoteProvider   ← 实盘：券商 Tick → QuoteSnapshot
        ├── TickflowQuoteProvider  ← 降级：未连接 / 研究模式
        └── RedisQuoteProvider     ← 降级：全市场榜 / 离线缓存
```

UI 层**不因切换行情源而重做**；新增 Gateway 实现 + 路由策略即可。

### 行情数据流

**当前（研究模式）：**

```
TickFlow API ──► 自选页（直连 / WebSocket）
Redis        ──► 市场页（需 quote_collector）
SQLite       ──► 本地 K 线（vnpy_sqlite）
```

**规划（Gateway 已连接时）：**

```
券商 Gateway ──► EVENT_TICK ──► GatewayQuoteProvider ──► 自选 / 市场页
                                      ↓（不可用则回退）
                              TickFlow / Redis
SQLite       ──► 本地 K 线（回测，与实盘 Tick 无关）
```

## AI 助手交互

AI 提供**悬浮球 + 全屏**两种形态：

| 模式 | 入口 | 说明 |
|------|------|------|
| 悬浮球 | 自选/市场/本地/选股页默认显示；`Ctrl+L` 切换显隐 | 左键开精简面板，右键快捷动作 |
| 全屏 | 导航「AI 助手」、面板「全屏」、回测「问 AI」 | 长对话与会话管理；回测问 AI 使用新会话 |
| 返回 | 全屏「← 返回看盘」 | 回到上次看盘页并打开悬浮面板 |

上下文通过 `QuoteService.publish_quote_context()` / `context_store.set_ai_context()` 写入，变更后 `LlmEngine.signals.context_changed` 驱动悬浮球角标与面板 ContextChip 更新。设计详见 [悬浮球功能增强设计](./superpowers/specs/2026-06-08-floating-orb-enhancement-design.md)。

回测摘要由 `BacktestService.persist_summary()` 统一写入（内存 + 落库 + context_store 缓存）；`get_backtest_result` 等 Skill 优先读 Service。

终端共享状态存放在 `ai/context_store.py`（线程安全内存）。**业务写入应经 Service**，Skills/LLM 只读可直接用 `context_store`：

| Service | 上下文职责 |
|---------|-----------|
| `QuoteService` | AI 页面上下文、市场行情缓存 |
| `ScreeningService` | 选股结果、选股页 AI 上下文 |
| `AnalysisService` | 诊断结果 |
| `BacktestService` | 回测摘要 |
| `BarService` | 数据管理页 AI 上下文 |

**Agent Skills 工具链：** 各业务 Skill（`skills/vnpy_*_skill.py`）继承 `SkillTemplate`，通过 `SkillEngine` 的 `services` 参数注入 `vnpy_ashare/services/` 层引用，提供 `get_watchlist`、`get_bars_summary`、`run_backtest`、`diagnose_stock` 等工具函数。

System Prompt 中 Agent Skill（`SKILL.md`）**仅注入名称与简介**；详细 API 文档通过 `read_skill_file` 按需加载，避免每次对话灌入全文。`ScreeningService` 统一从 context_store 行情缓存或 Redis 加载 quote 行，供 AI 选股与规则引擎共用。
