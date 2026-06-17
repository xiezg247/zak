# 盘中选股

> 操作速查见 [选股 Hub 使用指南](./screener-hub-guide.md)。

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

在 `composite_score` 合并后、取 `top_n` 前应用。GUI 面板：`ScreenerHardFilterPanel`（条件选股与多因子配方共用）；偏好持久化于 QSettings（`hard_filter_prefs.py`），环境变量仍可覆盖。

| 规则 | 默认 |
|------|------|
| 排除 ST / *ST | `name` 含 `ST`（不区分大小写） |
| 最低成交额 | ≥ 3000 万元（`amount` 元，阈值 3e7） |
| 排除停牌 | 默认开启（Tushare 停牌列表） |
| 排除新股 | 默认关闭；开启时上市满 60 日 |
| 排除涨跌停板 | 默认关闭 |
| 最低总市值 | 可选，默认 50 亿（`total_mv` 万元） |
| 行业白名单 | 可选；空表示不限（Tushare 行业映射） |
| 板块白名单 | 可选：沪深主板 / 创业板 / 科创板 / 北交所 |

**快捷模板**（面板「保守 / 均衡 / 激进」）：一键切换 ST、停牌、流动性、涨跌停等组合阈值。

环境变量（可选，优先于 QSettings）：

- `RECIPE_MIN_AMOUNT_YUAN`、`RECIPE_EXCLUDE_ST`、`RECIPE_EXCLUDE_SUSPENDED`
- `RECIPE_EXCLUDE_NEW_LISTING` / `RECIPE_MIN_LISTING_DAYS`
- `RECIPE_EXCLUDE_LIMIT_BOARD`、`RECIPE_MIN_TOTAL_MV_WAN`
- `RECIPE_ALLOWED_INDUSTRIES`（逗号分隔行业名）
- `RECIPE_ALLOWED_MARKET_BOARDS`（逗号分隔板块名）

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

### 2.5 极致短线 Recipe（规划 R-01–R-04）

> 状态与分期见 [implementation-roadmap.md §3](./implementation-roadmap.md#3-选股-reciper-)。实现前 Hub 仅内置 `intraday_multi`。

| ID | 名称 | trigger | 核心维度 | 用途 |
|----|------|---------|----------|------|
| R-01 | `ultra_short_limit` | intraday | 涨停 + 连板 + 板块强度 + 换手 | 极致短线主池（Phase 1） |
| R-02 | `ultra_short_first_board` | intraday | 首板 + 封板时间代理 + 题材 | 启动期试错 |
| R-03 | `cm20_elastic` | intraday | 涨幅 + 小盘 + 概念强度 | 20cm 弹性 |
| R-04 | `emotion_gate_only` | intraday | sentiment_gate × 其它配方 | 退潮期空池或 Top3 观察 |

**R-04 行为**：当 T-03 阶段为 `retreat`（退潮）时，其它 intraday 配方前置 gate，返回空结果或仅观察名单；与 [emotion-cycle.md](./emotion-cycle.md) gate 一致。

### 2.6 硬过滤模板「激进」（规划）

与 R-01 同批交付；在现有保守 / 均衡 / 激进三档中扩展 **激进** 默认值：

| 规则 | 激进模板值 | 均衡（现有默认） |
|------|------------|------------------|
| 最低成交额 | ≥ 5000 万 | 3000 万 |
| 流通市值带 | 30–200 亿（主板）/ 20–150 亿（创科） | 最低总市值 50 亿 |
| 排除 ST / 停牌 | 强制 | 强制 |
| 排除一字板 | 可选（打板场景可关） | — |
| 排除涨跌停 | 关（需含涨停池） | 可选 |

QSettings：`screener_ui/hard_filter_template=aggressive`；`RECIPE_*` env 仍可覆盖。

**退潮软拦截（T-06）**：情绪阶段为退潮时，结果操作条「加入自选」批量操作弹出确认，并建议改用 R-04 或空仓。

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

选股 Hub（`ScreenerHubPageWidget`）内嵌两个 Tab，共用布局组件（`screener_layout.py`）与结果洞察（`ScreenerResultInsights`）。

### 5.1 布局

```text
┌─ 主工具栏（运行 / 保存方案 / 导出 CSV / …）────────────────┐
├─ 左栏配置区（可滚动 Accordion）──┬─ 右栏结果区 ──────────────┤
│  ScreenerConfigSection 折叠分组    │  ScreenerResultActionBar   │
│  + ScreenerHardFilterPanel        │  ScreenerResultInsights    │
│                                   │  结果表 / 空态提示          │
└───────────────────────────────────┴──────────────────────────┘
```

- 左栏默认宽 380px（`SCREENER_CONFIG_DEFAULT_WIDTH`），分组展开状态持久化于 QSettings（`screener_ui`）。
- 结果区操作条（`ScreenerResultActionBar`）：有结果时显示全选、加入自选、下载日 K、策略回测、批量回测、找同类。

### 5.2 条件选股 Tab

| 左栏分组 | section_id | 内容 |
|----------|------------|------|
| 基础条件 | `condition_basic` | preset、Top N、自定义行情阈值 |
| 快捷选股 | `condition_quick` | 形态选股、雷达共振、行业成分 |
| 硬过滤 | `condition_hard_filter` | `ScreenerHardFilterPanel` |

顶栏：`ScreeningDataStatusBar`（交易时段 / 数据源 / 快照年龄；交易时段可「刷新行情」）。

### 5.3 多因子配方 Tab

| 左栏分组 | section_id | 内容 |
|----------|------------|------|
| 配方编辑 | `recipe_editor` | `ScreenerRecipePanel`、维度权重 |
| 硬过滤 | `recipe_hard_filter` | 与条件选股共用硬过滤面板 |

左侧运行历史收件箱支持 `[盘中]` / `[盘后]` 过滤。

### 5.4 结果洞察与导出

**ScreenerResultInsights**（可折叠，`result_insights`）：

- 文本：较上次 run diff（`run_diff.py`）
- 图表：`SectorDistributionPanel` 行业分布

**导出 CSV**（`screener/run/export.py`）：主工具栏「导出 CSV」，按结果字段自动选列集：

| 列集 | 触发条件 |
|------|----------|
| 行情 | 含 `last_price` 等实时字段 |
| 基本面 | 含 `pe_ttm`、`total_mv` 等 |
| 资金流 | 主力净流入为主、`moneyflow_source` |
| 配方 | Recipe 结果（综合分、入选原因、行业、变动状态） |

批量对话框（标杆对标等）亦支持导出。

### 5.5 相关 UI 模块

| 模块 | 路径 |
|------|------|
| 布局常量 | `ui/screener/widgets/screener_layout.py` |
| 折叠分组 | `ui/screener/widgets/screener_config_section.py` |
| 工具栏 / 结果操作条 | `ui/screener/widgets/screener_toolbars.py` |
| 硬过滤面板 | `ui/screener/widgets/screener_hard_filter_panel.py` |
| 结果表 | `ui/screener/widgets/screener_results_table.py` |
| 洞察面板 | `ui/screener/widgets/screener_insights.py` |

## 6. 风险与合规

| 风险 | 缓解 |
|------|------|
| Redis 无数据 | 三级降级 + 明确提示运行行情采集 |
| Tushare 不可用 | 量比维度降级为成交量排序 |
| AI 编造指标 | 解读强制 `get_screening_context` |
| 合规 | 不提供买卖价/仓位；免责声明保留 |

---

## 参考

- [选股 Hub 使用指南](./screener-hub-guide.md)
- [implementation-roadmap.md](./implementation-roadmap.md)（R-01–R-04）
- [emotion-cycle.md](./emotion-cycle.md)（R-04 gate）
- [产品说明 §选股 Hub](./product-plan.md#选股-hub)
- [架构说明 §选股 Hub](./architecture.md)
- [AI 数据路由 §选股](./ai-data-routing.md#选股)
- [数据设计 §1.8 screener_runs](./data-design.md#18-screener_runs--选股运行历史)
