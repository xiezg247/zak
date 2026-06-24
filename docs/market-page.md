# 市场页

> 全市场广度、排行、涨停池；择时与情绪周期的数据源之一。  
> `Ctrl+3`；代码：`ui/quotes/` + `quotes/market/`。

---

## 1. 能力

| 能力 | 短线意义 |
|------|----------|
| 涨跌家数、涨跌停计数 | 情绪周期输入 |
| 成交额汇总 | < 1 万亿橙色提示 |
| 涨幅/跌幅/换手排行 | 人气扫描 |
| 涨停榜 `limit_up` | 10cm 主池（含连板列） |
| 连板榜 `limit_times` | 侧栏按连板数排序 |
| 恐贪 + 北向环境 | sentiment、AI 择时 |
| 情绪周期芯片 | 顶栏阶段 + 建议仓位 |

---

## 2. 数据流

```text
Redis 快照 + Tushare
  → market_breadth / market_environment / 排行
  → emotion_cycle → 顶栏芯片、选股 gate、AI
```

详见 [情绪周期引擎](./emotion-cycle.md)。

---

## 3. 排行

| 排行 | rank_id | 数据源 |
|------|---------|--------|
| 涨幅/跌幅/换手 | 各 catalog | Redis / TickFlow |
| 涨停榜 | `limit_up` | 同上 |
| 连板榜 | `limit_times` | 同上 |

单击行 → 看盘页选中标的。

---

## 4. 广度条 stats_bar

上涨/下跌家数、涨停/跌停、两市成交额。连板梯队另见连板榜与雷达「发现·连板梯队」。

---

## 5. AI

「今日短线环境评估」→ `build_market_ai_prompt`（广度 + 环境 + 情绪 + 成交额）。

---

## 6. 与其它页

| 页 | 侧重 |
|----|------|
| 市场 | 全市场广度、排行 |
| 板块资金 | 行业/概念资金流向 |
| 雷达 | 多卡共振、龙头 |
| 选股 Hub | Recipe / 条件执行 |

---

## 参考

[情绪周期](./emotion-cycle.md) · [盘中工作流](./intraday-workflow.md) · [雷达页](./radar-page.md)
