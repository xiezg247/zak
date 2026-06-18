# 策略回测

A 股策略回测的交互与数据约定。引擎：vnpy `CtaBacktesterApp` + `AShareTemplate`。

## 用户流程

```text
选股 / 发现 → 加入自选 → 下载日 K → 策略回测
```

看盘页选中标的可一键带入回测页，预填 `vt_symbol`，不自动开始回测。

## 功能

| 功能 | 说明 |
|------|------|
| 看盘联动 | 自选/市场/本地 → 策略回测，预填代码 |
| 批量回测 | 自选/选股「批量回测」→ 回测对比页；`batch_watchlist` / `batch_screener` |
| 摘要落库 | `backtest_runs` 表；`BacktestService.persist_summary()` |
| AI 上下文 | 回测页与完成后写入 `context_store`；「问 AI」开全屏新会话 |
| 策略规则 | `AShareTemplate`：仅做多、100 股整手、T+1 |
| 默认参数 | `ensure_runtime_config()` 写入 A 股配置 |

## 流程细节

**看盘联动**：工具栏「策略回测」→ `EVENT_OPEN_BACKTEST` → 切换导航 + `BacktesterWidget.apply_vt_symbol()`。

**批量回测**：`ui/backtest/flow/batch_backtest_flow.py` 后台逐只回测 → 落库 `batch_id` → 跳转回测对比页。需本地已有日 K。

**批量回测模板（选股 / 自选）**：确认对话框提供「回测模板」下拉：

| 选项 | 说明 |
|------|------|
| 自动（跟随来源） | 龙头 → 日 K 打板；Recipe / Profile 推断 |
| 日 K · 极致短线打板/半路 等 | `batch_templates.py` 日 K 模板 |
| 分 K · 打板/半路/低吸/隔日退出 | 须本地 1m；确认时会提示 |

选中分 K 模板后，`BatchBacktestParams.interval` 为 `MINUTE`，缺 1m 的单只结果在对比表「备注」列标记错误。

**摘要与 AI**：回测完成后写入 `~/.vntrader/zak.db`，同步 `context_store` 供 Skill 与「问 AI」读取。

## 数据约定

**vt_symbol**：`{6位代码}.{SSE|SZSE|BSE}`

**默认参数**（`vnpy_ashare/config.py` → `ASHARE_BACKTEST_DEFAULTS`）：

| 字段 | 值 |
|------|-----|
| 股票代码 | `600519.SSE` |
| 每股乘数 | 1 |
| 价格跳动 | 0.01 |
| 手续费率 | 0.00045 |
| 滑点 | 0.01 |
| 资金 | 100000 |

**K 线下载**：

```bash
uv run python cli.py data download-batch --start 2020-01-01 --end 2026-06-08
# 分 K 打板回测（单票示例）
uv run python cli.py data download --symbol 600519 --exchange SSE --period 1m --start 2025-01-01 --end 2026-06-01
```

**分 K 回测（Phase 5）**：

| 策略 | 周期 | 数据要求 |
|------|------|----------|
| `AshareLimitBoardStrategy` | 日 K | 本地日 K（默认） |
| `AshareLimitBoardMinuteStrategy` | 1m | 本地 1 分 K（Tushare `stk_mins` 或 TickFlow Pro） |
| `AshareIntradayBreakoutMinuteStrategy` | 1m | 9:40–10:30 半路窗口 + 本地 1m |
| `AsharePullbackMinuteStrategy` | 1m | 14:30 后承接 + 本地 1m + 日 K |
| `AshareOvernightExitMinuteStrategy` | 1m | 隔日退出规则验证（日末建仓） |

批量回测模板 `ultra_short_*_minute` / `ultra_short_overnight_exit_minute` 可通过 `apply_batch_backtest_template(..., template_id=...)` 套用。

## 相关文件

| 文件 | 职责 |
|------|------|
| `app/events.py` | `EVENT_OPEN_BACKTEST`、`BacktestRequest` |
| `ui/backtest/flow/batch_backtest_flow.py` | 批量回测编排 |
| `ui/backtest/pages/batch_backtest_page.py` | 回测对比页 |
| `ui/quotes/controllers/batch_backtest.py` | 看盘页批量回测入口 |
| `backtest/run_store.py` | `backtest_runs` 表 |
| `services/backtest.py` | 摘要落库与 context |
| `ai/context/backtest.py` | 回测页 AI 上下文组装 |
| `strategies/ashare_template.py` | 策略基类 `AShareTemplate` |

---

## 参考

- [产品说明 §回测](./product-plan.md#回测)
- [AI 数据路由 §回测解读](./ai-data-routing.md#路由总表)
- [AI 功能与 K 线](./ai-kline-data.md)
- [数据设计 §backtest_runs](./data-design.md)
