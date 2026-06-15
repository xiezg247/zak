# 盘中选股

## 1. 概述

以 `recipe_runner` 为统一内核，支持盘中多因子维度并行打分、硬过滤与 AI 工具执行。与条件选股、定时任务共用结果落库与 `context_store` 注入。

```text
选股 Hub「条件选股」Tab ──► runner.run_screener ──► Redis / Tushare
选股 Hub「多因子配方」Tab ──► recipe_runner.run_recipe ──► 维度并行打分 ──► composite_score
定时任务 screen_intraday ──► jobs/auto_screen ──► intraday_multi
AI 对话 ──► vnpy-screening Skill ──► screen_by_* / run_recipe / propose_recipe
```

| 模块 | 路径 |
|------|------|
| Recipe 定义 | `screener/recipe.py` |
| 配方执行 | `screener/recipe_runner.py` |
| 行情 preset | `screener/rules.py`, `presets.py` |
| AI Skill | `skills/vnpy_screening_skill.py` |
| 定时盘中 | `jobs/auto_screen.py` |

## 2. 架构

```text
                    ┌─────────────────┐
                    │  vnpy-screening │
                    │  list_recipes   │
                    │  run_recipe     │
                    │  propose_recipe │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   recipe_runner        runner            pattern_screen
         │
         ▼
   dimension_registry ──► momentum / turnover / volume_ratio / ...
         │
         ▼
   recipe_filters（ST、成交额下限等）
         │
         ▼
   composite_score 合并 ──► persist_run_result ──► context_store
```

### 2.1 维度插件接口

```python
# screener/dimensions/registry.py
def run_dimension(spec: DimensionSpec, pool_size: int) -> tuple[list[DimensionHit], int]
```

每个维度独立文件，注册到 `DIMENSION_RUNNERS: dict[str, Callable]`。

### 2.2 维度目录

| dimension_id | 标签 | trigger | 数据源 |
|--------------|------|---------|--------|
| momentum | 动量 | intraday, post_close | Redis 涨幅 |
| turnover | 换手 | intraday | Redis 换手 |
| volume_ratio | 量比 | intraday | Tushare daily_basic + Redis 合并 |
| volume_surge | 放量 | intraday | Redis 成交量 |
| moneyflow | 资金 | post_close | Tushare moneyflow |
| low_pe | 估值 | post_close | Tushare daily_basic |
| sector_strength | 板块 | intraday | Redis + 行业映射 |
| concept_strength | 概念 | intraday | Redis + 概念映射 |
| intraday_breakout | 突破 | intraday | Redis 行情 + 可选分钟 K |
| moneyflow_intraday | 盘中资金 | intraday | TDX MCP / 成交额代理 |
| sentiment_gate | 环境 | intraday | vnpy-sentiment 权重调制 |

### 2.3 硬过滤

在 `composite_score` 合并后、取 `top_n` 前应用：

| 规则 | 默认 |
|------|------|
| 排除 ST / *ST | `name` 含 `ST`（不区分大小写） |
| 最低成交额 | ≥ 3000 万元（`amount` 元，阈值 3e7） |
| 排除停牌 | 默认开启（Tushare 停牌列表） |
| 排除新股 | 默认上市满 60 日 |
| 排除涨跌停板 | 默认开启（主板/创业板/科创板规则） |
| 最低总市值 | 可选，默认 50 亿（`total_mv` 万元） |

环境变量（可选，优先于 QSettings）：

- `RECIPE_MIN_AMOUNT_YUAN`、`RECIPE_EXCLUDE_ST`、`RECIPE_EXCLUDE_SUSPENDED`
- `RECIPE_EXCLUDE_NEW_LISTING` / `RECIPE_MIN_LISTING_DAYS`
- `RECIPE_EXCLUDE_LIMIT_BOARD`、`RECIPE_MIN_TOTAL_MV_WAN`

### 2.4 默认盘中配方 `intraday_multi`

| 维度 | 权重 |
|------|------|
| 动量 momentum | 0.28 |
| 量比 volume_ratio | 0.23 |
| 板块 sector_strength | 0.18 |
| 概念 concept_strength | 0.08 |
| 换手 turnover | 0.14 |
| 放量 volume_surge | 0.09 |

- `min_dimensions`: **2**
- `top_n`: 20
- `pool_size`: 80

## 3. AI + Skills

### 3.1 vnpy-screening 工具

| 工具 | 行为 |
|------|------|
| `list_recipes` | 列出内置/用户配方；可选 `trigger_kind=intraday\|post_close` |
| `run_recipe` | 直接执行配方并落库 |
| `propose_recipe` | NL → 配方草案（内存 TTL）；复杂/自定义时待确认 |

### 3.2 路由规则

| 用户表述 | 优先工具 |
|----------|----------|
| 盘中 / 现在 / 今天异动 / 多因子 | `run_recipe`（intraday）或 `list_recipes` |
| 涨幅榜 / 低 PE 等单一 preset | `screen_by_condition` |
| 形态（老鸭头等） | `screen_by_pattern` |
| 已保存方案 / 模糊条件 | `propose_screening` |
| 自定义多因子配方 | `propose_recipe` |
| 解读结果 | `get_screening_context` / `explain_screening_run` |

### 3.3 Skill 协作

| 场景 | 主 Skill | 辅助 |
|------|----------|------|
| 盘中强势股 | vnpy-screening | vnpy-sentiment |
| 板块 + 资金 | tdx-stock-picker | vnpy-screening |
| 结果解读 | vnpy-analysis | tdx-stock-diagnose |

## 4. 数据依赖

```text
行情采集 Job (60s) → Redis 全市场快照
市场页加载 → QuoteService 缓存（Skill 优先读缓存）
recipe 维度 → load_screening_quote_snapshot() / Tushare fallback
```

`quotes_loader` 行字段含 `amount`（成交额，元），供流动性过滤。量比维度：Tushare `daily_basic.volume_ratio` 与 Redis 按 `vt_symbol` 合并；Tushare 不可用时按 `volume` 降序降级。

选股前 `ensure_fresh_quotes_for_screening`；默认 cron `10:02/14:02`（`cron_minute_intraday=2`）。

## 5. UI

选股 Hub（`ScreenerHubPageWidget`）内嵌两个 Tab：

| Tab | 说明 |
|-----|------|
| 条件选股 | preset / 自定义条件；`ScreeningDataStatusBar` 展示数据源与快照年龄 |
| 多因子配方 | Recipe 运行与历史收件箱；左侧 `[盘中]` / `[盘后]` 过滤 |

两 Tab 共用 `ScreenerResultInsights`：文本 diff（`run_diff.py`）+ `SectorDistributionPanel` 行业分布。

## 6. 风险与合规

| 风险 | 缓解 |
|------|------|
| Redis 无数据 | 三级降级 + 明确提示运行行情采集 |
| Tushare 不可用 | 量比维度降级为成交量排序 |
| AI 编造指标 | 解读强制 `get_screening_context` |
| 合规 | 不提供买卖价/仓位；免责声明保留 |
