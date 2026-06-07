# 后续规划

本文档记录 vnpy_zak 的技术演进路线，含 **A 股策略实盘**（P3–P4）。**产品全景与迭代顺序**见 [product-plan.md](./product-plan.md)。

---

## 阶段概览

| 阶段 | 目标 | 状态 |
|------|------|------|
| P0 | 看盘终端（自选/市场/本地）、TickFlow、Redis、K 线、调度 | ✅ 已完成 |
| P1 | AI 助手（侧栏 + 全屏、上下文、会话持久化） | ✅ 已完成 |
| **P1.5** | **选股 MVP + 选股页 + 回测联动 + 批量回测 + AI 工具** | **见 product-plan、[backtest-ux](./backtest-ux.md)** |
| P2 | AI 增强（多会话、流式中断、配置热重载） | 规划中 |
| P3 | **A 股策略实盘**（Gateway、PaperAccount、CTA策略页、交易 Dock） | 已规划 |
| P4 | 看盘页 Gateway 行情主源、TickFlow/Redis 降级 | 随 P3 推进 |

---

## P1.5 子项：策略回测交互（见 [backtest-ux.md](./backtest-ux.md)）

| 迭代 | 内容 | 状态 |
|------|------|------|
| B1 | 看盘页「策略回测」按钮 → 跳转 + 预填 `vt_symbol` | ✅ 已完成 |
| B2 | 自选池批量回测对比表 | 未开始 |
| B3 | 回测摘要落库（AI 可读） | 未开始 |
| B4 | 回测页 AI 上下文 | 未开始 |

---

## P2：AI 助手增强（可选）

- [ ] 多会话列表与切换（`vnpy_llm/store.py` 已有 sessions 表，UI 未暴露）
- [ ] 工具调用：查本地 K 线、自选列表、涨跌幅（需定义 `vnpy_ashare/ai/tools`）
- [ ] 系统提示词按页面分化（自选 vs 回测 vs 数据管理）
- [ ] 流式输出中断（Stop 按钮）
- [ ] 配置页：模型 / API 热重载（不必重启 GUI）

---

## P3：A 股策略实盘

> **目标**：回测验证通过的 `AShareTemplate` 策略（如 `AshareDoubleMaStrategy`），在同一终端内以 **CTA策略** 模块跑 **A 股现货**自动交易（含 PaperAccount 模拟盘）。  
> **不是**期货 CTP / SimNow；vnpy「CTA」为策略框架名称，本项目的 A 股规则由 `AShareTemplate` 实现。

### 原则

1. **不替换**现有自建看盘页，在其上**增量叠加** vnpy 交易能力。
2. **策略代码复用**：回测与实盘共用 `strategies/` 下同一策略类，不维护两套逻辑。
3. **研究 vs 实盘**行情：未连接券商时 TickFlow/Redis；实盘/模拟盘优先 **A 股 Gateway** Tick，与下单同源。
4. **最大程度复用** vnpy 组件：`CtaStrategyApp`、`TradingWidget`、PaperAccount，少造轮子。

### 推荐 UI 结构

```
左侧导航（页面级）              右侧 Dock（操作级）
─────────────────              ─────────────────
自选 / 市场 / 本地  ← 主界面    AI 侧栏（已有）
交易监控          ← 新增       下单面板 TradingWidget（新增，默认隐藏）
策略回测 / 数据管理  ← 保持       委托 / 成交 / 持仓 Monitor（可选 Dock）
```

**CTA策略** 页（vnpy `CtaManager`）：**当前未启用**（左侧导航与 `CtaStrategyApp` 均已移除）。P3 实盘阶段再 `add_app(CtaStrategyApp)` 并加回导航；与 **策略回测** 分工——回测看历史，CTA策略跑盘中。

#### 1. 左侧导航：新增「交易监控」页

放**监控型、全屏**内容，不放完整下单表单：

- 当日委托 / 成交汇总
- 持仓 / 资金
- Gateway 连接状态
- 可选：券商 Tick 驱动的简化行情条

#### 2. 右侧 Dock：vnpy 原生交易组件

与 AI Dock 类似，默认隐藏，快捷键或菜单唤起（如 `Ctrl+T`）：

- `TradingWidget` — 下单
- `OrderMonitor` / `TradeMonitor` / `PositionMonitor`

实现参考：恢复 `MainWindow.create_dock()` 模式，在 `AshareMainWindow` 中新增 `_init_trading_dock()`，**不要**恢复整套默认 `init_dock()`。

#### 3. 自建看盘页：薄联动

- 选中股票 → 填充 `TradingWidget` 的合约代码
- 可选只读展示：持仓数量、可卖数量（读 OMS）
- **不在**看盘页嵌入第二套下单 UI

### 后端接入步骤

```text
1. 选型并安装 A 股 Gateway 包（如 vnpy_xtp、vnpy_torastock 等）
2. launcher：main_engine.add_gateway(AshareGateway)
3. launcher：main_engine.add_app(CtaStrategyApp)   # 恢复 CTA策略 页
4. launcher：main_engine.add_app(PaperAccountApp)   # 模拟盘
5. 左侧导航加回「CTA策略」入口
6. 系统菜单「连接」→ ConnectDialog（vnpy 已有）
7. _init_trading_dock()                            # 交易 Dock
8. 导航新增「交易监控」页
9. quotes_page 选股 → TradingWidget 联动
10. CTA策略页：添加 AshareDoubleMaStrategy → 初始化 → 启动
11. P4：看盘页切换 GatewayQuoteProvider（与策略 Tick 同源）
```

### 模拟盘路径（推荐先于实盘）

```text
连接 A 股 Gateway（仅需行情 + 合约查询）
    → 启动 PaperAccount（委托本地撮合，接口显示 PAPER）
    → CTA策略页运行 AShareTemplate 策略
    → 验证通过后再切换券商实盘/仿真账号
```

### 行情双源策略（概要）

| 场景 | 行情来源 | 说明 |
|------|----------|------|
| 研究 / 回测 / 未连接券商 | TickFlow + Redis | 现状默认 |
| 实盘（Gateway 已连接） | 券商实时 Tick | 与委托、持仓同一数据源 |
| 模拟盘（PaperAccount） | A 股 Gateway 行情 + 本地撮合 | 与实盘共用 CTA策略 页与策略类 |
| 仅研究、未连接券商 | TickFlow + Redis | 现状默认 |

---

## P4：看盘页切换为券商行情（Gateway 优先）

有券商接口后，**看盘页可改以 Gateway 为主源**，TickFlow / Redis **降级为备用**，无需重做 UI。

### 原则

1. **UI 不变**：`QuotesPage` 继续消费 `QuoteSnapshot`。
2. **扩展 Provider**：在 `QuoteProvider` 上新增 `GatewayQuoteProvider`，不修改页面布局。
3. **自动回退**：Gateway 未连接、非交易时段、订阅失败时，回退 TickFlow / Redis。
4. **K 线独立**：历史 / 回测 K 线仍走 TickFlow + SQLite，不与实盘 Tick 混用。

### 目标架构

```text
QuotesPage / QuotesRefreshWorker / TickflowStreamBridge（可选改造）
        ↓
   get_quote_provider(page, mode)
        ↓
   ┌─────────────────────────────────────┐
   │ QUOTE_MODE=auto | gateway | tickflow │
   └─────────────────────────────────────┘
        ↓
   auto：Gateway 已连接 → GatewayQuoteProvider
         否则           → TickflowQuoteProvider / RedisQuoteProvider
```

### 配置项（规划）

```env
# 行情模式：auto（推荐）| gateway | tickflow
QUOTE_MODE=auto

# gateway 模式下，市场涨幅榜是否仍用 Redis（券商无全市场快照时）
MARKET_RANK_FALLBACK=redis
```

### GatewayQuoteProvider 实现要点

| 环节 | 说明 |
|------|------|
| 事件订阅 | 监听 `EVENT_TICK`，按 `vt_symbol` 更新内存 cache |
| 类型转换 | `TickData` → `QuoteSnapshot`（最新价、昨收、涨跌等字段映射） |
| 符号映射 | `600519.SSE` ↔ 券商代码，在 Gateway 或适配层统一 |
| 自选刷新 | `get_quotes(items)` 从 cache 读取；缺失则触发 `subscribe` 或回退 TickFlow |
| 五档 / WS | 若券商提供 Level-2，可替代 `TickflowStreamBridge`；否则回退或隐藏五档 |
| 市场榜 | 若券商无涨幅榜 API，市场页继续 `RedisQuoteProvider` 或改为「持仓 + 自选」列表 |

### 降级后 TickFlow / Redis 的保留价值

| 组件 | 降级后用途 |
|------|------------|
| **TickFlow** | 无券商账户、批量下 K、历史分钟线、Gateway 不可用时的看盘 |
| **Redis + quote_collector** | 全市场涨幅榜、降低 TickFlow 调用频率、离线缓存 |
| **TickflowStreamBridge** | Gateway 无 WS 时的五档 / 推送回退 |
| **SQLite K 线库** | 图表、CTA 回测（长期不变） |

### 实现步骤（建议顺序）

```text
1. GatewayQuoteProvider：Tick cache + TickData → QuoteSnapshot
2. provider.py：get_quote_provider() 支持 QUOTE_MODE 路由
3. quotes_page / worker：自选刷新走统一 Provider（替代硬编码 TickFlow）
4. Gateway 连接状态变化时，刷新 Provider 并提示当前行情源
5. （可选）Gateway 模式下用 EVENT_TICK 推送到 chart_panel，替代 TickFlow WS
6. 状态栏或设置页展示：当前源 = 券商 / TickFlow / Redis
```

### 风险与约束

- **订阅数量**：券商常限制同时订阅标的数；自选过多时需「仅订阅当前选中 + 可见行」或分批。
- **交易时段**：休市无 Tick 时显示昨收或回退 TickFlow 静态快照。
- **数据一致性**：实盘下单场景下，同一标的的行情与持仓必须同源（Gateway）；研究模式允许 TickFlow。
- **市场页**：全市场 5000+ 标的无法全部订阅 Gateway，市场榜宜保留 Redis 或改为有限榜单。

### 与 P3 交易模块的关系

| 模块 | 关系 |
|------|------|
| P3 交易 Dock | 下单、委托、持仓（vnpy 原生组件） |
| P4 Gateway 看盘 | 同一 Gateway 的 Tick 驱动看盘页，与下单数据一致 |
| 执行顺序 | 可先 P3（仅交易 + TickMonitor），再 P4（看盘页切 Provider）；或一次接入 Gateway 后并行 |

---

## P5：其他可选项

- [ ] **QuestDB**：大数据量 K 线 / 盘中写入（见根目录 README）
- [ ] **Tushare 选股脚本**：财务、资金流筛选，结果导入自选池
- [ ] **自选页工具栏 AI 图标**：`Ctrl+L` 的可视化入口（当前仅菜单 + 快捷键）
- [ ] **vnpy_ashare / vnpy_llm 拆包发布**：独立 pip 包时的路径与配置解耦
- [ ] **日志 Dock**：调试 Gateway / 调度时可选开启

---

## 明确不做（除非需求变更）

- 用 vnpy 默认 Trader 布局**替换**自建看盘页
- 在主导航为 AI 单独占一格（已采用方案 B：叠加层）
- **期货** CTP / SimNow 作为本项目的交易或行情通道
- 无券商连接时默认强制走 Gateway（应回退 TickFlow）
- 回测与实盘维护两套独立策略代码
- 废弃 TickFlow / Redis（实盘阶段降级为备用，不删除）

---

## 文档维护

架构或规划变更时，同步更新：

- `docs/architecture.md` — 现状结构
- `docs/roadmap.md` — 本文件
- 根目录 `README.md` — 用户可见的快速开始（保持精简）
