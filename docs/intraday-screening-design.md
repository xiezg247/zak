# 盘中选股功能设计

> 版本：Phase 3（2026-06-10）  
> 状态：Phase 1–3 已完成

## 1. 背景与目标

zak 终端已有「策略选股」「自动选股（Recipe 多因子）」「AI 对话选股」三条路径，但盘中能力薄弱：

- 内置盘中配方 `intraday_multi` 仅 **动量 + 换手** 两维；
- AI Skill 无法直接执行 Recipe（只有 `screen_by_condition` / `screen_by_pattern`）；
- 缺 ST / 流动性硬过滤；`min_dimensions=1` 过松；
- 解读链路未与 `get_screening_context`、诊断 Skill 闭环。

**目标**：以 `recipe_runner` 为统一内核，扩展盘中维度插件、补齐 AI 工具、加强过滤，为 Phase 2（板块、解读编排）打基础。

## 2. 现状架构

```text
策略选股页 ──► runner.run_screener ──► Redis / Tushare
自动选股页 ──► recipe_runner.run_recipe ──► 维度并行打分 ──► composite_score
定时任务 screen_intraday ──► jobs/auto_screen ──► intraday_multi
AI 对话 ──► vnpy-screening Skill ──► screen_by_* / propose_screening
```

关键模块：

| 模块 | 路径 |
|------|------|
| Recipe 定义 | `screener/recipe.py` |
| 配方执行 | `screener/recipe_runner.py` |
| 行情 preset | `screener/rules.py`, `presets.py` |
| AI Skill | `skills/vnpy_screening_skill.py` |
| 定时盘中 | `jobs/auto_screen.py` |

## 3. 目标架构（Phase 1）

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
   dimension_registry ──► momentum / turnover / volume_ratio / volume_surge / ...
         │
         ▼
   recipe_filters（ST、成交额下限）
         │
         ▼
   composite_score 合并 ──► persist_run_result ──► context_store
```

### 3.1 维度插件接口

```python
# screener/dimensions/registry.py
def run_dimension(spec: DimensionSpec, pool_size: int) -> tuple[list[DimensionHit], int]
```

每个维度独立文件，注册到 `DIMENSION_RUNNERS: dict[str, Callable]`。

### 3.2 维度目录（Phase 1 落地）

| dimension_id | 标签 | trigger | 数据源 | Phase |
|--------------|------|---------|--------|-------|
| momentum | 动量 | intraday, post_close | Redis 涨幅 | 已有 |
| turnover | 换手 | intraday | Redis 换手 | 已有 |
| volume_ratio | 量比 | intraday | Tushare daily_basic + Redis 合并 | **P1** |
| volume_surge | 放量 | intraday | Redis 成交量 | **P1** |
| moneyflow | 资金 | post_close | Tushare moneyflow | 已有 |
| low_pe | 估值 | post_close | Tushare daily_basic | 已有 |
| sector_strength | 板块 | intraday | Redis + 行业映射 | P2 |
| intraday_breakout | 突破 | intraday | Redis 行情 + 可选分钟 K | **P3** |
| moneyflow_intraday | 盘中资金 | intraday | TDX MCP / 成交额代理 | **P3** |
| sentiment_gate | 环境 | intraday | vnpy-sentiment 权重调制 | **P3** |

### 3.3 硬过滤（Phase 1）

在 `composite_score` 合并后、取 `top_n` 前应用：

| 规则 | 默认 |
|------|------|
| 排除 ST / *ST | `name` 含 `ST`（不区分大小写） |
| 最低成交额 | ≥ 3000 万元（`amount` 元，阈值 3e7） |

环境变量（可选）：

- `RECIPE_MIN_AMOUNT_YUAN`：覆盖成交额下限（元）
- `RECIPE_EXCLUDE_ST`：`0` 关闭 ST 过滤

### 3.4 升级后的默认盘中配方

`intraday_multi`（内置，向后兼容 recipe_id）：

| 维度 | 权重 |
|------|------|
| 动量 momentum | 0.35 |
| 量比 volume_ratio | 0.30 |
| 换手 turnover | 0.20 |
| 放量 volume_surge | 0.15 |

- `min_dimensions`: **2**（须至少命中 2 个维度）
- `top_n`: 20
- `pool_size`: 80

## 4. AI + Skills（Phase 1）

### 4.1 新增工具（vnpy-screening）

| 工具 | 行为 |
|------|------|
| `list_recipes` | 列出内置/用户配方；可选 `trigger_kind=intraday\|post_close` |
| `run_recipe` | 直接执行配方并落库；意图明确时用 |
| `propose_recipe` | NL → 配方草案（内存 TTL）；复杂/自定义时待确认 |

### 4.2 路由规则（prompts / router）

| 用户表述 | 优先工具 |
|----------|----------|
| 盘中 / 现在 / 今天异动 / 多因子 | `run_recipe`（intraday）或 `list_recipes` |
| 涨幅榜 / 低 PE 等单一 preset | `screen_by_condition` |
| 形态（老鸭头等） | `screen_by_pattern` |
| 已保存方案 / 模糊条件 | `propose_screening` |
| 自定义多因子配方 | `propose_recipe` |
| 解读结果 | `get_screening_context` |

### 4.3 Skill 协作矩阵（Phase 2+）

| 场景 | 主 Skill | 辅助 |
|------|----------|------|
| 盘中强势股 | vnpy-screening | vnpy-sentiment |
| 板块 + 资金 | tdx-stock-picker | vnpy-screening |
| 结果解读 | vnpy-analysis | tdx-stock-diagnose |

## 5. 数据依赖

```text
行情采集 Job (60s) → Redis 全市场快照
市场页加载 → QuoteService 缓存（Skill 优先读缓存）
recipe 维度 → load_screening_quote_snapshot() / Tushare fallback
```

`quotes_loader` 行字段扩展：`amount`（成交额，元），供流动性过滤。

量比维度：Tushare `daily_basic.volume_ratio` 与 Redis 行情按 `vt_symbol` 合并；Tushare 不可用时按 `volume` 降序降级。

## 6. UI（Phase 1 不变，Phase 2 增强）

Phase 1 不新增导航；沿用「自动选股」页 + 左侧 `[盘中]` 过滤。

Phase 2 计划：结果 diff、板块分布、`propose_recipe` 确认对话框。

## 7. 实施分期

### Phase 1（已完成）

- [x] 设计文档（`docs/intraday-screening-design.md`）
- [x] `dimension_registry` 重构，迁移 4 维（`screener/dimensions/`）
- [x] 新增 `volume_ratio`、`volume_surge`
- [x] `list_recipes` / `run_recipe` / `propose_recipe`（`vnpy-screening` Skill）
- [x] 更新 `prompts.py`、`ai-data-routing.md`、`router.py`、`context.py`
- [x] `intraday_multi` 四维 + `min_dimensions=2` + ST/成交额硬过滤

### Phase 2（已完成）

- [x] `sector_strength` 维度（`screener/dimensions/sector_strength.py`）
- [x] `intraday_multi` 升级为五维（含板块 20%）
- [x] `explain_screening_run` 解读编排（`vnpy-analysis` Skill）
- [x] 同配方 run diff（`run_diff.py` + 结果表 `diff_status` 列）
- [x] `propose_recipe` UI 确认对话框（`recipe_confirm_dialog.py`）
- [x] `tdx-stock-picker` 与路由文档同步

### Phase 3（已完成）

- [x] `intraday_breakout`（昨收突破 + 接近日内高点；可选 `BREAKOUT_MINUTE_CONFIRM=1` 分钟 K 确认）
- [x] `moneyflow_intraday`（`MCP_INTRADAY_FLOW=1` 时 TDX MCP；默认成交额+涨幅代理）
- [x] `sentiment_gate` 恐贪权重调制（盘中配方默认 `RECIPE_SENTIMENT_GATE=1`）
- [x] 选股前 `ensure_fresh_quotes_for_screening`；默认 cron `10:02/14:02`（`cron_minute_intraday=2`）

## 8. 风险与合规

| 风险 | 缓解 |
|------|------|
| Redis 无数据 | 三级降级 + 明确提示运行行情采集 |
| Tushare 不可用 | 量比维度降级为成交量排序 |
| AI 编造指标 | 解读强制 `get_screening_context` |
| 合规 | 不提供买卖价/仓位；免责声明保留 |

## 9. 验收标准（Phase 1）

1. `run_recipe("intraday_multi")` 返回含 `composite_score`、`dimensions`、`hit_reason` 的结果；
2. 至少命中 2 个维度才入选；ST 与低成交额标的被过滤；
3. AI 对话「跑盘中多因子」可调用 `run_recipe` 并落库；
4. `list_recipes(trigger_kind="intraday")` 返回配方目录；
5. 现有 `test_recipe_runner` 与 screening skill 测试通过。
