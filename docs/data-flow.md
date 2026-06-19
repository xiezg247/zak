# 数据流与触发方式

说明 zak 各类数据**何时加载、由谁触发**，避免在 App 启动或 UI 主线程做全市场重算。

## 四档触发

| 档位 | 时机 | 典型数据 | 原则 |
|------|------|----------|------|
| **冷启动** | 打开 App | 本地 SQLite、磁盘持仓/信号缓存 | 只读已有数据；**不**拉 Redis 全市场 |
| **打开页面** | Tab `activate()` | 当前页行情、雷达单卡 | Worker + 页面内 QTimer；无缓存则占位 |
| **定时任务** | Scheduler / CLI `job run` | 全市场因子、选股、摘要预热 | 批量、可离线、写缓存 |
| **用户触发** | 按钮 / 记账 / AI | 试跑选股、回测、流水 | 强交互、参数多变 |

```text
冷启动 ──► 只读本地 / 内存缓存
              │
打开市场/雷达/自选 ──► 轻量 Timer + Worker（仅当前页）
              │
定时任务 ──► Redis / SQLite / 内存摘要缓存
              │
用户操作 ──► 即时执行（可 force）
```

## 定时任务（后台 → 定时任务）

与 `commands/jobs.py` 共用实现。推荐盘后顺序：

```text
prefetch_moneyflow (16:31)
  → prefetch_tushare (16:32)        # 结束后轻量预热情绪
  → prefetch_concept_board (16:33)
  → warm_market_summary (16:34)     # 情绪周期预热（盘后补全因子）
  → sync_suspend / sync_sector_flow …
  → screen_post_close → scan_horizon_outlook
```

| job_id | 说明 |
|--------|------|
| `collect_quotes` | 交易时段 TickFlow → Redis；**成功后自动轻量预热情绪** |
| `prefetch_concept_board` | 同花顺概念指数与成分映射 |
| `warm_market_summary` | 情绪周期 → 内存缓存 |
| `prefetch_tushare` | daily_basic、涨跌停等；**成功后轻量预热情绪** |
| 其余 | 见定时任务页描述 |

盘中：`collect_quotes` + 轻量 `warm_market_summary(enrich_factors=False)`。

## 页面内定时（仅 Tab 激活时）

| 页面 | 机制 | 间隔（约） |
|------|------|------------|
| 市场页概览 | `MarketOverviewLoadWorker` | 30s（交易时段） |
| 市场列表 | 行情自动刷新 | 用户可关 |
| 雷达卡片 | 每卡 QTimer | 60s+ 可配 |
| 自选信号/持仓 | Controller Timer | 5min |
| 情绪芯片 | 读缓存；缺失则后台 Worker | 不阻塞启动 |

## 内存摘要缓存

| 缓存 | 写入 | 读取 |
|------|------|------|
| 行情行 | `set_market_quote_rows_cache` / QuoteService | `load_emotion_cycle_snapshot(fetch_if_missing=False)` |
| 情绪周期 | `store_emotion_cycle_snapshot` | 持仓风控、雷达 subtitle、工具栏芯片 |

UI 与 `load_combined_risk_gate_snapshot` **默认不拉全市场**；显式分析/流水仍可用 `fetch_if_missing=True`。

## 用户触发（不宜默认定时）

- 选股 Hub「运行」、雷达刷新、回测、登记买卖、交易计划、AI 分析
- `工具 → 立即执行 → <job>`（等同 CLI `job run --force`）

## 相关文档

- [市场页](./market-page.md) · [情绪周期](./emotion-cycle.md)
- [盘中选股](./intraday-screening.md) · [消息通知](./notifications.md)
- [数据设计](./data-design.md)
