# 盘中选股（技术说明）

> **操作向**文档见 [选股 Hub 使用指南](./screener-hub-guide.md)。

---

## 1. 数据流

```text
条件选股 Tab → run_screener → Redis / Tushare
多因子 Tab   → recipe_runner → 维度打分 → composite_score → 硬过滤
定时任务     → screen_intraday → intraday_multi
AI           → vnpy-screening → screen_by_* / run_recipe
```

结果：`persist_run_result` → `screener_runs` + `context_store`。

核心路径：`screener/recipe_runner.py`、`screener/run/`、`jobs/auto_screen.py`。

---

## 2. 多因子维度

| dimension_id | 数据源 |
|--------------|--------|
| momentum / turnover / volume_surge | Redis |
| volume_ratio / low_pe / moneyflow | Tushare + Redis |
| sector_strength / concept_strength | Redis + 映射 |
| intraday_breakout | Redis + 可选分 K |
| sentiment_gate | 恐贪权重调制 |

---

## 3. 硬过滤

`ScreenerHardFilterPanel` 两 Tab 共用；QSettings 持久化，`RECIPE_*` 环境变量可覆盖。

| 规则 | 默认 |
|------|------|
| 排除 ST / 停牌 | 开 |
| 最低成交额 | 3000 万 |
| 排除新股 / 涨跌停 / 市值 / 行业·板块白名单 | 可配 |

模板：**保守 / 均衡 / 激进**（极致短线用激进：5000 万成交额、市值带 30–200 亿等）。Profile 切换会联动模板。

退潮期：批量「加入自选」弹出确认。

---

## 4. 内置配方

### `intraday_multi`（默认盘中）

动量 0.28 · 量比 0.23 · 板块 0.18 · 换手 0.14 · 放量 0.09 · 概念 0.08；`top_n=20`，`min_dimensions=2`。

### 极致短线

| 配方 | 用途 |
|------|------|
| `ultra_short_limit` | 涨停 + 连板主池 |
| `ultra_short_first_board` | 首板 |
| `cm20_elastic` | 20cm |
| `emotion_gate_only` | 退潮观察 |
| `ultra_short_unified` | 龙头 + 共振统一池（`top_n=12`） |

`emotion_gate_only`：退潮时其它 intraday 配方前置 gate。

---

## 5. AI 路由

| 表述 | 工具 |
|------|------|
| 盘中多因子 | `run_recipe` / `list_recipes` |
| 涨幅榜等 preset | `screen_by_condition` |
| 形态 | `screen_by_pattern` |
| 复杂条件 | `propose_screening` / `propose_recipe`（确认后执行） |
| 解读 | `get_screening_context` |

详见 [AI 数据路由](./ai-data-routing.md)。

---

## 6. 数据依赖

交易时段需 Redis 行情（`collect_quotes` Job）。量比维度 Tushare 不可用时降级为成交量排序。  
默认盘中 cron：10:02 / 14:02。

---

## 参考

[选股 Hub](./screener-hub-guide.md) · [情绪周期](./emotion-cycle.md) · [数据设计](./data-design.md) · [架构说明](./architecture.md)
