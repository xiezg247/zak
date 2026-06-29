# 策略回测

引擎：vnpy `CtaBacktesterApp` + `AShareTemplate`（仅做多、100 股整手、T+1）。

```text
选股/发现 → 自选 → 下载日 K → 策略回测 → 摘要落库 → AI 解读
```

看盘选中标的 →「策略回测」预填 `vt_symbol`（`EVENT_OPEN_BACKTEST`），打开菜单栏弹窗，不自动开跑。

## 入口

菜单栏「回测」：`策略回测…`（`Ctrl+Shift+8`）· `回测对比…`（`Ctrl+Shift+9`）。非模态弹窗，关闭后保留表单/对比状态；自选、选股、AI 深链同样打开弹窗，不切主内容页。

## 批量回测

自选/选股「批量回测」→ `batch_backtest_flow.py` → `batch_id` 落库 → 打开「回测对比」弹窗。须本地日 K。

确认框可选模板：**自动**（跟随龙头/Recipe/Profile）、日 K 极致短线、分 K 打板/半路/低吸/隔日退出。分 K 须本地 1m，缺数据在对比表「备注」标错。

## 数据

`vt_symbol`：`{代码}.{SSE|SZSE|BSE}`。默认见 `ASHARE_BACKTEST_DEFAULTS`（手续费 0.00045、资金 10 万等）。

```bash
uv run python cli.py data download-batch --start 2020-01-01 --end 2026-06-08
uv run python cli.py data download --symbol 600519 --exchange SSE --period 1m --start 2025-01-01
```

分 K 策略：`AshareLimitBoardMinuteStrategy`、`AshareIntradayBreakoutMinuteStrategy`、`AsharePullbackMinuteStrategy`、`AshareOvernightExitMinuteStrategy` 等。批量模板 `ultra_short_*_minute`。

完成后写入 PG `app.backtest_runs` + `context_store`。代码：`ui/backtest/`、`services/backtest.py`。

---

[AI 数据路由](./ai-data-routing.md) · [AI 与 K 线](./ai-kline-data.md) · [数据设计](./data-design.md)
