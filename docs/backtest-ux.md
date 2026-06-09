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

## 2. 实现状态（2026-06）

### 2.1 已实现

| 项 | 说明 |
|----|------|
| 策略规则 | `AShareTemplate`：仅做多、100 股整手、T+1 |
| 默认参数 | `ensure_runtime_config()` 写入 `~/.vntrader/cta_backtester_setting.json`；检测期货配置自动重置 |
| 回测页包装 | `BacktesterWidget`：标题「策略回测」、字段中文化、策略下拉仅 `AShareTemplate` 子类 |
| K 线数据 | `batch_download` / 数据管理 → SQLite `database.db`，与回测引擎 `get_database()` 同源 |
| 数据源 | TickFlow / Tushare（`init_config.py` → `vt_setting.json`） |
| 回测摘要落库 **B3** | `backtest/run_store.py` → `~/.vntrader/zak.db` 表 `backtest_runs`；`BacktestService.persist_summary()` 写入 |
| 回测页 AI 上下文 **B4** | `ai/backtest_context.py` → `context_store.set_ai_context()`；「问 AI」走全屏新会话 |
| 批量回测对比 **B2** | 自选页 / 选股页「批量回测」→ `batch_backtest_flow.py` →「回测对比」页；落库 `source=batch_watchlist` / `batch_screener` |

### 2.2 未实现 / 远期

| 项 | 优先级 | 说明 |
|----|--------|------|
| 策略实盘 | P3 | 远期规划，暂无近期计划，见 [roadmap.md](./roadmap.md) |

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

### 迭代 B2：批量回测对比 ✅ 已实现

#### 入口

| 页面 | 操作 | 数据源 |
|------|------|--------|
| **自选** | 工具栏「批量回测」 | 自选池（`WatchlistService` / `load_watchlist_rows`） |
| **选股** | 勾选结果 →「批量回测」 | 当前选股结果表 |
| **回测对比** | 左侧导航独立页 | 历史批次（`backtest_runs.batch_id`） |

#### 行为

1. 弹出策略 / 日期配置对话框（共用 `ScreenerBatchBacktestConfigDialog`）
2. 后台逐只调用 `BacktesterEngine.run_backtesting`（`screener/batch_actions.run_batch_backtests`）
3. 结果落库 `backtest_runs`（带 `batch_id`），并跳转 **回测对比** 页
4. 对比表列：代码、名称、总收益、最大回撤、夏普、交易次数；支持导出 CSV、删除批次、跳转单只策略回测

#### 技术方案

```text
自选页 QuotesPage / 选股页 ScreenerPage
    → ui/batch_backtest_flow.BatchBacktestFlow
        → ScreenerBatchBacktestWorker
        → persist_batch_backtest_results(source=batch_watchlist | batch_screener)
        → EVENT_OPEN_BATCH_BACKTEST → ui/batch_backtest_page.py
```

#### 验收标准

- [x] 自选池非空时可发起批量回测
- [x] 选股页勾选多行可批量回测
- [x] 完成后可在「回测对比」查看批次并导出 CSV

#### 依赖

- 本地日 K 已下载（无数据时单只回测失败，错误写入对比表「备注」列）

---

### 迭代 B3：回测摘要落库 ✅ 已实现

#### 目的

供 AI 工具 `get_backtest_summary` 与历史对比，见 [product-plan.md](./product-plan.md) §4.4。

#### 存储

- 路径：`~/.vntrader/zak.db`（`APP_DB_PATH`）表 `backtest_runs`
- 实现：`vnpy_ashare/backtest/run_store.py`
- 字段：`id`、`vt_symbol`、`strategy`、`interval`、`start_date`、`end_date`、`total_return`、`max_drawdown`、`sharpe_ratio`、`trade_count`、`source`、`batch_id`、`raw_statistics_json`、`created_at`

#### 写入时机

- 单次回测完成：`BacktesterWidget.process_backtesting_finished_event` → `BacktestService.persist_summary()`
- 同步内存与 `context_store` 缓存，供回测页 AI 与 Skill 读取

---

### 迭代 B4：回测页 AI 上下文 ✅ 已实现

- 进入策略回测页：`sync_backtest_page_context()` 经 `BacktestService` / `context_store` 推送当前表单与最近摘要
- 完成回测后：摘要落库 + `context_store` 缓存更新
- 「问 AI」：`EVENT_ASK_AI` + `new_session=True`，prompt 含 `format_backtest_summary_text()` 输出
- 实现：`vnpy_ashare/ai/backtest_context.py`、`ui/backtest_widget.py`

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
| `vnpy_ashare/events.py` | `EVENT_OPEN_BACKTEST`、`EVENT_OPEN_BATCH_BACKTEST`、`BacktestRequest` |
| `vnpy_ashare/ui/quotes/page_shell.py` | 自选页「策略回测」「批量回测」按钮 |
| `vnpy_ashare/ui/quotes/batch_backtest_controller.py` | 自选页批量回测入口 |
| `vnpy_ashare/ui/batch_backtest_flow.py` | 自选 / 选股共用批量回测流程 |
| `vnpy_ashare/ui/batch_backtest_page.py` | B2：回测对比页 |
| `vnpy_ashare/screener/batch_actions.py` | 批量回测执行与落库 |
| `vnpy_ashare/ui/main_window.py` | 导航切换与事件订阅 |
| `vnpy_ashare/ui/backtest_widget.py` | `apply_vt_symbol()`、回测完成摘要落库、「问 AI」 |
| `vnpy_ashare/backtest/run_store.py` | B3：`backtest_runs` 表读写 |
| `vnpy_ashare/services/backtest_service.py` | 摘要内存 + 落库 + `context_store` 同步 |
| `vnpy_ashare/ai/backtest_context.py` | B4：回测页 AI 上下文组装 |
| `vnpy_ashare/ai/context_store.py` | 终端共享内存（AI 上下文、回测摘要缓存等） |
| `vnpy_ashare/config.py` | A 股回测默认参数 |
| `strategies/ashare_template.py` | 策略基类 `AShareTemplate` |
| `strategies/double_ma_strategy.py` | 默认示例策略 `AshareDoubleMaStrategy` |
| `strategies/registry.py` | 策略元数据注册表 `STRATEGY_REGISTRY` |

---

## 6. 修订记录

| 日期 | 内容 |
|------|------|
| 2026-06 | 初版：盘点 + B1–B4 分阶段规格 |
| 2026-06 | B1 实现：`EVENT_OPEN_BACKTEST`、看盘工具栏「策略回测」按钮 |
| 2026-06 | B3/B4 实现：`run_store`、`BacktestService`、`backtest_context`；`session_context` 已移除，统一 `context_store` |
| 2026-06 | B2 实现：自选 / 选股批量回测、`batch_backtest_flow`、回测对比页 |
