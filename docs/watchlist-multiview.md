# 自选页多维看盘

> **UI 架构**（`features/watchlist/`、Host 协议）见 [watchlist-ui.md](./watchlist-ui.md)。

## 1. 功能概述

自选页工具栏提供 **表格 / 多维** 视图切换。多维视图以卡片网格同时展示自选池全部标的的价量、异动指标、迷你图，以及与信号区 / 持仓 / 板块的关联角标。

| 项 | 约定 |
|----|------|
| 页面范围 | 仅自选页（`show_watchlist_multiview=True`） |
| 默认视图 | 表格（`QSettings` 无记录时） |
| 自选池上限 | 50 只（`WATCHLIST_MAX_ITEMS`） |
| 网格列数 | 2 / 3 / 4 列，默认 3，持久化 |

## 2. 布局

```text
┌─ 工具栏 ─────────────────────────────────────────────┐
│ [搜索] [表格|多维] …                               │
│ 多维区顶栏：摘要 · [排序▾] [列数▾]                 │
├──────────────────────────────┬─────────────────────┤
│ 表格 或 多维卡片网格           │ 右侧图表 / 五档 / 笔记 │
│ 策略信号区（保留）             │                     │
│ 持仓区（保留）                 │                     │
└──────────────────────────────┴─────────────────────┘
```

中央区通过 `QStackedWidget` 在 `MarketTableHost` 与 `WatchlistMultiViewBoard` 间切换；信号区、持仓区、右侧详情区布局不变。

## 3. 模块结构

```text
quotes/watchlist_multiview/          # 领域层
├── models.py
├── loader.py                        # 行情 + 异动分
├── enrich.py                        # 信号 / 持仓 / 板块 / 迷你图
├── sparkline_data.py                # 日 K / 分时迷你图数据
├── sort.py
└── summary.py                       # AI 整板摘要

ui/quotes/watchlist_multiview/     # UI 层
├── settings.py                      # QSettings
├── card.py                          # 单票卡片
├── sparkline.py                     # 迷你图组件
├── panel.py                         # 网格容器
├── controller.py                    # 刷新编排、联动
└── worker.py                        # 迷你图后台加载
```

## 4. 卡片维度

| 维度 | 来源 |
|------|------|
| 价量 | TickFlow / Redis 行情（复用 `radar_watchlist` enrich） |
| 异动分 | `_intraday_score`，角标阈值 ≥ 12 |
| 迷你图 | 跟随右侧图表 Tab：分时 / 日K / 分K |
| 信号角标 | 信号区名单 + `signal_cache` |
| 持仓角标 | `position_cache` 浮盈 |
| 板块角标 | Tushare 行业 + 市场页行情缓存行业榜 |

## 5. 交互

| 操作 | 行为 |
|------|------|
| 单击卡片 | 同步主表选中 → 右侧图表 / 笔记 / AI |
| 双击卡片 | 打开 `StockAnalysisDialog` |
| 右键卡片 | 复用自选主表右键菜单（下载、AI 分析等） |
| 排序 | 自选顺序 / 涨幅 / 异动分 |
| 列数 | 2 / 3 / 4 列 |

## 6. 刷新策略

| 类型 | 周期 / 触发 |
|------|-------------|
| 行情 | 沿用自选页 3s 行情刷新 |
| 信号 / 持仓 | 信号区 / 持仓区 Worker 完成 |
| 分时 / 分K 迷你图 | 进入多维视图 + 每 60s（仅交易时段，且右侧 Tab 为分时或分K） |
| 日 K 迷你图 | 进入多维视图；下载日 K 后增量刷新 |
| 板块 | 依赖市场页 `get_market_quotes_cache()` |

## 7. AI 上下文

多维视图激活时，`build_multiview_board_summary()` 生成整板摘要注入 `signal_extra`，示例：

```text
自选多维：共 12 只，涨 7 / 跌 4 / 平 1；信号区 1买入；持仓 2 只，均浮盈 +1.20%
```

## 8. QSettings

| Key | 默认 |
|-----|------|
| `watchlist/multiview/view_mode` | `table` |
| `watchlist/multiview/sort_key` | `sort_order` |
| `watchlist/multiview/grid_columns` | `3` |

## 9. 测试

| 文件 | 覆盖 |
|------|------|
| `tests/ashare/quotes/test_watchlist_multiview.py` | loader、sort、enrich、summary、settings、sparkline_data |

---

## 参考

- [自选策略信号区](./watchlist-signals.md)
- [看盘页个股笔记](./stock-notes.md)
- [产品说明 §自选](./product-plan.md#左侧导航)
