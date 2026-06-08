# 策略回测：交互与数据规格

本文档定义 **A 股策略回测** 的用户流程、数据依赖与分阶段交付标准。产品优先级见 [product-plan.md](./product-plan.md) §4.2；底层引擎为 vnpy `CtaBacktesterApp` + 项目 `AShareTemplate`。

---

## 1. 目标

打通投研闭环中的回测环节：

```text
选股 / 发现 → 加入自选 → 下载日 K → 策略回测验证 →（远期）同一策略实盘
```

用户不应在「看盘页选中的股票」与「回测页股票代码」之间手动复制粘贴。

---

## 2. 现状盘点（2026-06）

### 2.1 已适配

| 项 | 说明 |
|----|------|
| 策略规则 | `AShareTemplate`：仅做多、100 股整手、T+1 |
| 默认参数 | `ensure_runtime_config()` 写入 `~/.vntrader/cta_backtester_setting.json`；检测期货配置自动重置 |
| 回测页包装 | `BacktesterWidget`：标题「策略回测」、字段中文化、策略下拉仅 `AShareTemplate` 子类 |
| K 线数据 | `batch_download` / 数据管理 → SQLite `database.db`，与回测引擎 `get_database()` 同源 |
| 数据源 | TickFlow / Tushare（`init_config.py` → `vt_setting.json`） |

### 2.2 缺口

| 项 | 优先级 | 说明 |
|----|--------|------|
| 看盘 → 回测联动 | **B1** | 选中标的后一键跳转并预填 `vt_symbol` |
| 自选池批量回测 | B2 | 多标的同一策略，输出对比表 |
| 回测摘要落库 | B3 | 收益/回撤/夏普供 AI `get_backtest_summary` 读取 |
| 回测页 AI 上下文 | B4 | 侧栏知晓当前回测标的与最近结果 |
| 分钟回测 | B5 | 依赖 TickFlow 分钟 K 本地量（远期） |

---

## 3. 分阶段交付

### 迭代 B1：看盘 → 策略回测联动 ✅ 已实现

#### 入口

自选 / 市场 / 本地 三页工具栏新增 **「策略回测」** 按钮：

- 有选中行时启用，无选中时禁用
- 与「下载日 K 到本地」并列，表示「对当前标的做历史验证」

#### 行为

1. 用户在看盘页选中一行（`StockItem`）
2. 点击「策略回测」
3. 主窗口切换左侧导航至 **策略回测**
4. 回测表单 **股票代码** 预填 `{symbol}.{exchange}`（如 `600519.SSE`）
5. **不自动**点击「开始回测」——用户可改日期、策略后再跑
6. 日志区提示：`已从{自选|市场|本地}带入股票代码：600519.SSE`

#### 技术方案

```text
QuotesPage（工具栏按钮）
    → EventEngine.put(EVENT_OPEN_BACKTEST, BacktestRequest)
        → AshareMainWindow._on_open_backtest_event（后台线程，仅 emit Signal）
            → _handle_open_backtest（GUI 主线程）
                → 切换导航 + BacktesterWidget.apply_vt_symbol()
```

- 事件定义：`vnpy_ashare/events.py`
- 与 `EVENT_AI_CONTEXT` 同级，不经过 LLM 引擎
- `BacktestRequest` 字段：`vt_symbol`、`source_page`（自选/市场/本地）、`name`（可选，仅日志）

#### 非目标（B1 不做）

- 不预填开始/结束日期（沿用上次回测或 JSON 默认）
- 不从市场页批量带入多标的
- 不检查本地是否已有 K 线（无数据时由回测引擎报错，用户可点「下载数据」）

#### 验收标准

- [x] 自选页选中茅台 → 策略回测 → 代码为 `600519.SSE`
- [x] 市场页、本地页同样可用
- [x] 未选中时按钮灰色不可点
- [x] 已在回测页时再次从看盘带入，仅更新股票代码，不重置其它字段

---

### 迭代 B2：自选池批量回测（未开始）

#### 入口（拟定）

- 策略回测页新增「批量回测」子区，或
- 自选页工具栏「批量回测」

#### 行为（拟定）

1. 数据源：当前自选池列表（`app_db.load_watchlist_rows`）
2. 共用：策略类、日期区间、费率/滑点/资金
3. 逐只调用 `BacktesterEngine.run_backtesting`（或封装 runner）
4. 输出：表格列 = 代码、名称、总收益、最大回撤、夏普、交易次数
5. 支持导出 CSV

#### 依赖

- B1 完成单标的流程验证
- 本地日 K 已下载（或批量前提示下载）

---

### 迭代 B3：回测摘要落库（未开始）

#### 目的

供 AI 工具 `get_backtest_summary` 与历史对比，见 [product-plan.md](./product-plan.md) §4.4。

#### 存储（拟定）

- 路径：`~/.vntrader/vnpy_zak.db` 新表 `backtest_runs`，或 JSON 目录 `backtest_summaries/`
- 字段：`id`、`vt_symbol`、`strategy`、`interval`、`start`、`end`、`total_return`、`max_drawdown`、`sharpe`、`trade_count`、`created_at`、`raw_statistics`（JSON）

#### 写入时机

- 单次回测完成事件 `EVENT_BACKTESTER_BACKTESTING_FINISHED` 钩子（在 `BacktesterWidget` 或独立 listener）

---

### 迭代 B4：回测页 AI 上下文（未开始）

- 进入策略回测页或完成回测后，通过 `session_context.set_ai_context()` 推送：
  - 当前 `vt_symbol`、策略名、最近回测摘要（依赖 B3）
- 系统提示词分化：「你正在协助用户解读 A 股策略回测结果…」

---

## 4. 数据与参数约定

### 4.1 vt_symbol 格式

```text
{6位代码}.{SSE|SZSE|BSE}
```

与 vnpy、`StockItem.vt_symbol`、回测 JSON 一致。

### 4.2 回测默认参数（A 股）

| 字段 | 值 | 说明 |
|------|-----|------|
| 股票代码 | `600519.SSE` | 可被 B1 覆盖 |
| 每股乘数 | `1` | vnpy 字段 `size` |
| 价格跳动 | `0.01` | |
| 手续费率 | `0.00045` | 佣金万二 + 印花税万五折中 |
| 滑点 | `0.01` | |
| 资金 | `100000` | |

定义见 `vnpy_ashare/config.py` → `ASHARE_BACKTEST_DEFAULTS`。

### 4.3 K 线前置条件

回测前需本地有对应标的日 K：

```bash
uv run python scripts/batch_download.py --start 2020-01-01 --end 2026-06-08
```

或在回测页 / 数据管理中使用「下载数据」。

---

## 5. 相关文件

| 文件 | 职责 |
|------|------|
| `vnpy_ashare/events.py` | `EVENT_OPEN_BACKTEST`、`BacktestRequest` |
| `vnpy_ashare/ui/page_shell.py` | 「策略回测」按钮与事件发送 |
| `vnpy_ashare/ui/main_window.py` | 导航切换与事件订阅 |
| `vnpy_ashare/ui/backtest_widget.py` | `apply_vt_symbol()` |
| `vnpy_ashare/config.py` | A 股回测默认参数 |
| `strategies/ashare_template.py` | 策略基类 `AShareTemplate` |
| `strategies/double_ma_strategy.py` | 默认示例策略 `AshareDoubleMaStrategy` |
| `strategies/registry.py` | 策略元数据注册表 `STRATEGY_REGISTRY` |

---

## 6. 修订记录

| 日期 | 内容 |
|------|------|
| 2026-06 | 初版：盘点 + B1–B5 分阶段规格 |
| 2026-06 | B1 实现：`EVENT_OPEN_BACKTEST`、看盘工具栏「策略回测」按钮 |
