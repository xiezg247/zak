# 市场页

`Ctrl+3`。全市场广度、排行、涨停池；情绪周期数据源之一。代码：`ui/quotes/`、`quotes/market/`。

---

## 能力

| 能力 | 短线意义 |
|------|----------|
| 涨跌家数、涨跌停 | 情绪周期输入 |
| 成交额 | < 1 万亿橙色提示 |
| 涨幅/跌幅/换手排行 | 人气扫描 |
| 涨停榜 `limit_up` / 连板榜 `limit_times` | 10cm 主池、连板排序 |
| 恐贪 + 北向 | sentiment、AI 择时 |
| 顶栏情绪芯片 | 阶段 + 建议仓位 |

数据：Redis + Tushare → `market_breadth` / `market_environment` → `emotion_cycle`。详见 [情绪周期](./emotion-cycle.md)。

单击排行行 → 看盘选中。AI：「今日短线环境」→ `build_market_ai_prompt`。

---

## 与其它页

| 页 | 侧重 |
|----|------|
| 市场 | 全市场广度、排行 |
| 板块资金 | 行业/概念资金 |
| 雷达 | 多卡共振、龙头 |
| 选股 Hub | Recipe / 条件执行 |

---

[盘中工作流](./intraday-workflow.md) · [雷达页](./radar-page.md)
