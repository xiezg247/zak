# 演进路线

**产品全景**见 [product-plan.md](./product-plan.md)。**近期交付范围**（P0–P2）已全部实现；P3–P4 保留在路线图中作**远期参考**，**暂无近期实施计划**。

---

## 阶段概览

| 阶段 | 目标 | 状态 |
|------|------|------|
| P0 | 看盘终端（自选/市场/本地）、TickFlow、Redis、K 线、调度 | ✅ |
| P1 | AI 助手（侧栏 + 全屏、上下文、会话持久化） | ✅ |
| P1.5 | 选股 + 回测联动 + Agent Skills + Service 层 | ✅ |
| P2 | AI 增强（多会话 UI、流式 Stop、LLM 配置热重载） | ✅ |
| P3 | A 股策略实盘（Gateway、PaperAccount、CTA 策略页、交易 Dock） | 📋 远期 |
| P4 | 看盘页 Gateway 行情主源（TickFlow/Redis 降级） | 📋 远期（随 P3） |

---

## 已完成摘要

### 回测与选股（[backtest-ux.md](./backtest-ux.md)）

| 项 | 状态 |
|----|------|
| B1 看盘 → 策略回测联动 | ✅ |
| B2 自选 / 选股批量回测 + 回测对比页 | ✅ |
| B3 回测摘要落库 | ✅ |
| B4 回测页 AI 上下文 | ✅ |
| S1 选股模块 `screener/` | ✅ |
| S2 选股 GUI 页 | ✅ |

### AI 助手（P1 + P2）

- 悬浮球 + Dock + 全屏；`context_store` + 6 个 Service 写入上下文
- Agent Skills（`vnpy_*_skill.py`）+ MCP 远端工具
- 多会话（侧栏 / 「历史会话」弹窗）；流式 **停止**；`.env` **重载 LLM**
- 设置页（`.env` ↔ `vt_setting.json` 漂移检测）

### 其他

- 本地页 K 线健康检测与补全（`bar_health` + `local_data_controller`）
- 本地页 **批量补全过期** 日 K（`jobs/local_fill.py`）
- 本地页 **批量修复断层** 日 K（`jobs/local_fill.py`）
- 主窗口 **日志 Dock**（vnpy `LogMonitor`，`Ctrl+Shift+L`）
- 配置单源（`config_schema` / `config_bridge` / `settings_dialog`）

---

## 远期规划（P3–P4，暂无近期计划）

> 以下保留设计备忘，便于日后若接入券商 Gateway 或切换时序库时参考。**当前产品重心为投研闭环维护与可选增强**（见下文「近期可选」），不排期实盘 / 模拟盘 / QuestDB 开发。

## P3：A 股策略实盘（远期）

> **目标**：回测验证通过的 `AShareTemplate` 策略（如 `AshareDoubleMaStrategy`），在同一终端内以 **CTA 策略** 模块跑 **A 股现货**自动交易（含 PaperAccount 模拟盘）。  
> **不是**期货 CTP / SimNow。

### 原则

1. **不替换**现有自建看盘页，在其上**增量叠加** vnpy 交易能力。
2. **策略代码复用**：回测与实盘共用 `strategies/` 下同一策略类。
3. **研究 vs 实盘**行情：未连接券商时 TickFlow/Redis；实盘/模拟盘优先 **A 股 Gateway** Tick。
4. **复用** vnpy：`CtaStrategyApp`、`TradingWidget`、PaperAccount。

### 推荐 UI 结构

```
左侧导航（页面级）              右侧 Dock（操作级）
─────────────────              ─────────────────
自选 / 市场 / 本地  ← 已有      AI 侧栏（已有）
交易监控          ← 新增       下单面板 TradingWidget（新增）
策略回测 / 数据管理  ← 已有       委托 / 成交 / 持仓 Monitor（可选）
CTA 策略          ← 恢复挂载
```

**CTA 策略** 页：当前 `launcher` **未**加载 `CtaStrategyApp`；P3 接入 Gateway 时恢复。

### 后端接入步骤

```text
1. 选型并安装 A 股 Gateway 包（vnpy_xtp、vnpy_torastock 等）
2. launcher：main_engine.add_gateway(AshareGateway)
3. launcher：main_engine.add_app(CtaStrategyApp)
4. launcher：main_engine.add_app(PaperAccountApp)
5. 导航加回「CTA 策略」；系统菜单「连接」→ ConnectDialog
6. _init_trading_dock() + 「交易监控」页
7. quotes_page 选股 → TradingWidget 联动
8. CTA 策略页：加载 AshareDoubleMaStrategy → 初始化 → 启动
9. P4：GatewayQuoteProvider
```

### 模拟盘路径（推荐先于实盘）

```text
连接 A 股 Gateway（行情 + 合约查询）
    → PaperAccount（本地撮合，接口显示 PAPER）
    → CTA 策略页运行 AShareTemplate 策略
    → 验证通过后再切换券商实盘/仿真账号
```

---

## P4：看盘页 Gateway 行情（远期，随 P3）

有券商接口后，看盘页可改以 **Gateway 为主源**，TickFlow / Redis **降级备用**；UI 仍消费 `QuoteSnapshot`，新增 `GatewayQuoteProvider` + `QUOTE_MODE` 路由即可。K 线历史仍走 TickFlow + SQLite。

详见下文「GatewayQuoteProvider 要点」与原 P4 设计（配置项 `QUOTE_MODE=auto`、订阅数量限制、市场榜回退 Redis 等）。

### GatewayQuoteProvider 要点

| 环节 | 说明 |
|------|------|
| 事件订阅 | `EVENT_TICK` → 内存 cache |
| 类型转换 | `TickData` → `QuoteSnapshot` |
| 自动回退 | Gateway 未连接 → Tickflow / Redis |
| 市场榜 | 券商无全市场快照时保留 Redis |

---

## 数据层远期：QuestDB（暂无近期计划）

> **现状**：K 线与回测默认 **SQLite**（`vnpy_sqlite`），已满足当前日 K 投研闭环。  
> **触发条件（远期）**：全市场分钟 K 体量显著增大、盘中高频写入、或 SQLite 成为瓶颈时，再评估切换 [vnpy_questdb](https://github.com/vnpy/vnpy_questdb)。

仓库已保留可选接入（`uv sync --extra questdb`、`docker-compose.yml`、`scripts/start_questdb.sh`、`.env` 中 `QUESTDB_*`），**当前不排期**。

切换步骤备忘（日后实施时参考）：

```bash
uv sync --extra questdb
bash scripts/start_questdb.sh
# .env: DATABASE_NAME=questdb，并取消注释 QUESTDB_* 配置
uv run python scripts/init_config.py
uv run python scripts/check_database.py
```

切回 SQLite：`.env` 设 `DATABASE_NAME=sqlite`，重新执行 `init_config.py`。

---

## 近期可选（非阻塞）

当前若无新需求，**不启动 P3–P4**。近期已完成：

- 本地页 **批量补全过期** 日 K（`jobs/local_fill.py`）
- 本地页 **批量修复断层** 日 K（`jobs/local_fill.py`）
- 主窗口 **日志 Dock**（`Ctrl+Shift+L` 切换）

其余可优先考虑：

- 更多 `AShareTemplate` 示例策略（突破、RSI 等）
- `vnpy_ashare` / `vnpy_llm` 拆包发布
- AI 对话**全自动选股**（内置 preset → `screen_by_condition`；形态 → `screen_by_pattern`；复杂条件保留 `propose_screening` 确认）✅

（日志 Dock 已实现，见主窗口「工具 → 显示/隐藏 日志 Dock」。）

---

## 明确不做

- 用 vnpy 默认 Trader 布局**替换**自建看盘页
- 主导航为 AI 单独占一格（已采用叠加层方案）
- **期货** CTP / SimNow
- 回测与实盘维护两套策略代码
- 废弃 TickFlow / Redis（实盘阶段为降级备用）

---

## 文档维护

架构或规划变更时同步：`docs/architecture.md`、`docs/product-plan.md`、根目录 `README.md`。
