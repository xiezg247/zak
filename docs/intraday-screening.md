# 盘中选股（技术说明）

操作步骤见 [选股 Hub](./screener-hub-guide.md)。

---

## 1. 数据流

```text
条件选股 → run_screener → Redis / Tushare
多因子   → recipe_runner → composite_score → 硬过滤
定时任务 → screen_intraday → intraday_multi
AI       → screen_by_* / run_recipe / propose_*
```

落库：`screener_runs` + `context_store`。路径：`screener/recipe_runner.py`、`screener/run/`、`jobs/auto_screen.py`。

---

## 2. 多因子维度

| dimension_id | 数据源 |
|--------------|--------|
| momentum / turnover / volume_surge | Redis |
| volume_ratio / low_pe / moneyflow | Tushare + Redis |
| sector_strength / concept_strength | Redis + 映射 |
| intraday_breakout | Redis + 可选分 K |
| sentiment_gate | 恐贪权重调制 |

默认盘中 `intraday_multi`：动量 0.28 · 量比 0.23 · 板块 0.18 · 换手 0.14 · 放量 0.09 · 概念 0.08；`top_n=20`。

极致短线配方：`ultra_short_limit`、`ultra_short_first_board`、`cm20_elastic`、`emotion_gate_only`、`ultra_short_unified`（`top_n=12`）。退潮时其它 intraday 配方前置 gate。总纲见 [交易体系 §3](./trading-system.md#3-选股)。

---

## 3. 硬过滤

`ScreenerHardFilterPanel` 两 Tab 共用；QSettings 持久化，`RECIPE_*` 可覆盖。

| 规则 | 默认 |
|------|------|
| 排除 ST / 停牌 | 开 |
| 最低成交额 | 3000 万 |
| 新股 / 涨跌停 / 市值 / 行业·板块白名单 | 可配 |

模板：**保守 / 均衡 / 激进**（极致短线激进：5000 万成交额、市值 30–200 亿等）。Profile 切换联动模板。退潮期批量「加入自选」弹确认。

---

## 4. 依赖与 AI

交易时段需 Redis（`collect_quotes`）；量比维度 Tushare 不可用时降级成交量排序。默认 cron：10:02 / 14:02。

AI 工具：`run_recipe`、`screen_by_condition`、`screen_by_pattern`、`propose_*`、`get_screening_context`。见 [AI 数据路由](./ai-data-routing.md)。

---

[情绪周期](./emotion-cycle.md) · [数据设计](./data-design.md)
