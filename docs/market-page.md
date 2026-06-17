# 市场页说明

> **定位**：全市场**广度、排行、涨停池**的一屏概览；择时输入（T-01/T-02）与情绪周期（T-03）的数据源之一。  
> 导航：`Ctrl+2`；代码：`ui/quotes/` 市场子视图 + `quotes/market/`。

---

## 1. 页面职责

| 能力 | 状态 | 短线意义 |
|------|------|----------|
| 涨跌家数、涨跌停计数 | **已有** T-01 | 情绪周期输入 |
| 成交额汇总 | **已有** | < 1 万亿降仓提示（规划） |
| 涨幅 / 跌幅 / 换手排行 | **已有** | 人气扫描 |
| 涨停榜 `limit_up` | **已有** | 10cm 主池来源；缺连板梯队 |
| 恐贪 + 北向环境 | **已有** T-02 | sentiment_gate、AI 择时 |
| 情绪周期芯片 | **已有** T-04 | 顶栏阶段 + 建议仓位 |
| 连板梯队视图 | **待建** | 与 D-01 / G-01 合并规划 |

---

## 2. 与择时链关系

```text
Redis 全市场快照 + Tushare 补充
        │
        ├─► market_breadth ──► stats_bar（涨跌停、涨跌比）
        ├─► market_environment ──► 恐贪、北向
        └─► limit_up 排行 ──► 涨停池（连板字段已有，梯队 UI 待建）
                │
                ▼
        emotion_cycle（T-03）
                │
                ├─► 顶栏芯片 T-04
                ├─► Recipe R-04 gate
                └─► AI get_emotion_cycle
```

详见 [情绪周期引擎](./emotion-cycle.md)。

---

## 3. 排行与表格

| 排行 | 数据源 | 备注 |
|------|--------|------|
| 涨幅榜 | Redis / TickFlow | 交易时段优先 Redis |
| 跌幅榜 | 同上 | — |
| 换手榜 | 同上 | — |
| 涨停榜 | 同上 + 连板列 | Phase 2 按 `limit_times` 分层 |

单击行 → 看盘页选中标的（与自选页行为一致）。

---

## 4. 广度条 stats_bar

展示项（与 `market_breadth` 对齐）：

- 上涨 / 下跌家数
- 涨停 / 跌停家数（含 ST 可选过滤）
- 两市成交额（规划：与 1 万亿阈值对比着色）

**Phase 1**：广度数据 feed 给 T-03，不在本页重复展示复杂梯队（梯队优先雷达 D-01）。

---

## 5. AI 入口（规划）

| 动作 | 工具 / 上下文 |
|------|---------------|
| 「今日短线环境评估」 | T-01 + T-02 + T-03 + 成交额 |
| 选中标的问 AI | `get_quote_context` + 市场广度摘要 |

路由见 [AI 数据路由 §择时扩展](./ai-data-routing.md#择时与短线工具规划)。

---

## 6. 与其它页分工

| 页 | 侧重 |
|----|------|
| **市场** | 全市场广度、排行、涨停列表 |
| **板块资金** | 行业/概念**资金**流向 |
| **雷达** | 多卡共振、龙头评分、选股任务结果 |
| **选股 Hub** | Recipe / 条件执行与历史 run |

---

## 7. 数据依赖

| 数据 | 来源 |
|------|------|
| 实时行情 | Redis（`QUOTE_COLLECT_INTERVAL` 调度） |
| 恐贪 | `vnpy-sentiment` / Tushare |
| 北向 | Tushare |
| 连板次数 | 行情 enrich 或 Tushare `limit_list_d`（规划统一） |

离线 / Redis 空：顶栏数据状态条提示；AI 与选股引导打开市场页或运行行情采集 Job。

---

## 8. 相关文档

| 文档 | 内容 |
|------|------|
| [emotion-cycle.md](./emotion-cycle.md) | T-03 判定规则 |
| [intraday-workflow.md](./intraday-workflow.md) | 盘前看广度 |
| [radar-page.md](./radar-page.md) | 雷达 vs 市场分工 |
| [trading-system.md §2](./trading-system.md) | 择时需求 T-01–T-06 |
| [implementation-roadmap.md](./implementation-roadmap.md) | ID 状态 |
