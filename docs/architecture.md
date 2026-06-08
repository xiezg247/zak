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
| `vnpy_ashare/ai` | A 股上下文共享（`context.py` 等）、AI 全屏页 |

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

上下文通过 `session_context.set_ai_context()` 写入，变更后 `LlmEngine.signals.context_changed` 驱动悬浮球角标与面板 ContextChip 更新。设计详见 [悬浮球功能增强设计](./superpowers/specs/2026-06-08-floating-orb-enhancement-design.md)。

选股/回测时通过 `vnpy_ashare/ai/context.py` 的 `set_ai_context()` / `set_backtest_summary()` 共享上下文给 Agent Skills，避免事件广播耦合。

**Agent Skills 工具链：** 各业务 Skill（`skills/vnpy_*_skill.py`）继承 `SkillTemplate`，通过 `SkillEngine` 的 `services` 参数注入 `vnpy_ashare/services/` 层引用，提供 `get_watchlist`、`get_bars_summary`、`run_backtest`、`diagnose_stock` 等工具函数。
