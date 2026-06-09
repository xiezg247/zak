# vnpy_zak AI 能力重构与业务整合 技术设计方案

> 日期：2026-06-08  
> 状态：**已实现**（2026-06；P0–P4、P6 主体完成）

**实现摘要：** `vnpy_ashare/services/` 六 Service 已落地；Skills 按业务域拆分；Agent Skill 改为摘要注入；`EVENT_AI_CONTEXT` 已移除；原 `session_context.py` 已删除，终端共享状态统一为 `ai/context_store.py`，业务写入经 Service。

---

## 一、背景与目标

### 1.1 背景

vnpy_zak 已初步集成 AI 能力（LLM 对话 + Skills + MCP），但存在以下问题：

1. **AI 工具与业务割裂** — 只能"读"状态（查 K 线、看自选、读回测摘要），不能"做"操作（触发回测、执行选股）
2. **架构耦合** — Skills 直接 import `vnpy_ashare` 内部模块（`bar_store`、`bars`、`session_context`），跨层调用
3. **全局状态依赖** — ~~回测摘要通过 `session_context._backtest_summary` 传递~~ → 已改为 `BacktestService` + `context_store`
4. **上下文传递低效** — ~~`EVENT_AI_CONTEXT` 事件广播~~ → 已改为 Service setter + `context_store` listener
5. **Token 浪费** — System Prompt 中每次注入完整 SKILL.md 正文
6. **策略知识未暴露** — `strategies/registry.py` 的 `StrategyMeta` 仅在 UI 中显示，LLM 完全不知道

### 1.2 目标

1. **Service 层抽取** — 将散落在 UI/worker/工具函数中的业务能力抽象为可复用 Service
2. **Skills 按业务域拆分** — 从 1 个 Skill 拆为 5 个，Tools 4→16+
3. **AI 上下文优化** — 分层知识注入、去掉事件广播、策略知识暴露
4. **MCP 保持现状** — 远端数据源定位清晰，不做大改

---

## 二、架构变更

### 2.1 改造前

```
QuotesPage → EVENT_AI_CONTEXT → LlmEngine → SkillEngine
                                              ├─ VnpyContextSkill (1个/4工具)
                                              │   ├─ import bar_store ← 跨层耦合
                                              │   ├─ import bars
                                              │   └─ import session_context ← 全局变量
                                              └─ Agent Skills (2个 SKILL.md)
                                                 └─ 完整 body 注入 System Prompt
```

### 2.2 改造后

```
QuotesPage → quote_service.set_selection()     ← 一行 setter
    
LlmEngine
  ├─ SkillEngine(services={"bar":..., "backtest":..., ...})
  │   ├─ VnpyContextSkill     ← 仅上下文
  │   ├─ VnpyDataSkill        ← K线/行情/财务 (依赖 BarService+QuoteService)
  │   ├─ VnpyBacktestSkill    ← 触发回测+查询 (依赖 BacktestService)
  │   ├─ VnpyScreeningSkill   ← 选股 (依赖 ScreeningService)
  │   ├─ VnpyWatchlistSkill   ← 自选管理 (依赖 WatchlistService)
  │   └─ Agent Skills          ← 摘要注入，按需 read_skill_file
  └─ McpEngine                 ← 远端 MCP，不变

Service 层 (vnpy_ashare/services/)
  ├─ BarService               ← 聚合 bar_store + bars
  ├─ QuoteService             ← 持有上下文状态 + 行情查询
  ├─ BacktestService          ← 回测生命周期管理
  ├─ ScreeningService         ← 选股条件执行 (全新)
  └─ WatchlistService         ← 自选池 CRUD
```

---

## 三、详细设计

### 3.1 vnpy_ashare/services/ — Service 层

#### 3.1.1 BaseService

```python
# vnpy_ashare/services/base.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnpy_ashare.engine import AshareEngine
    from vnpy.event import EventEngine
    from vnpy.trader.engine import MainEngine


class BaseService:
    """Service 基类，通过 AshareEngine 注入依赖。"""

    def __init__(self, engine: AshareEngine) -> None:
        self.engine = engine
        self.main_engine: MainEngine = engine.main_engine
        self.event_engine: EventEngine = engine.event_engine
```

#### 3.1.2 BarService（K线查询）

```python
# vnpy_ashare/services/bar_service.py
# 职责：K线概览、历史数据加载、区间统计
# 聚合 bar_store.get_period_overview + bar_store.load_scope_bars + bar_store.iter_bar_overviews
# 新增方法：
#   get_overview(symbol, exchange, scope) → PeriodBarOverview | None
#   load_bars(symbol, exchange, scope, start, end) → list[BarData]
#   get_return(symbol, exchange, scope, lookback_days) → dict (区间涨跌摘要)
#   list_downloaded(scope) → list[PeriodBarOverview]
```

#### 3.1.3 QuoteService（行情查询 + 上下文状态）

```python
# vnpy_ashare/services/quote_service.py
# 职责：持有当前选中标的上下文状态，行情信息查询
# 替代 session_context.py 中的全局变量
# 方法：
#   set_current_selection(symbol, exchange, page, quote, bar_count) → 简单 setter
#   get_current_context() → AiContextData
#   get_quote(symbol) → QuoteSnapshot | None
#   get_market_rank(top_n) → list (涨幅榜)
```

#### 3.1.4 BacktestService（回测生命周期）

```python
# vnpy_ashare/services/backtest_service.py
# 职责：触发回测、管理结果摘要
# 替代 session_context.py 中的 BacktestSummary 全局变量
# 方法：
#   list_strategies() → list[StrategyMeta]
#   run_backtest(strategy, vt_symbol, start, end, interval, capital) → BacktestSummary
#   get_last_summary() → BacktestSummary | None
#   clear_summary()
```

#### 3.1.5 ScreeningService（选股）

```python
# vnpy_ashare/services/screening_service.py
# 职责：执行选股条件，返回候选标的
# 全新模块，基于现有数据能力构建
# 方法：
#   list_screeners() → list (可用选股条件名称)
#   screen_by_condition(name, top_n) → list[Candidate]
#   screen_custom(conditions) → list[Candidate]
# 内置条件：
#   - 涨幅榜：按 change_pct 排序取 top_n
#   - 换手率：按 turnover_rate 排序
#   - 成交量放大：volume > MA(volume, 20) * threshold
#   - 均线金叉：fast_ma 上穿 slow_ma（需本地 K 线数据）
```

#### 3.1.6 WatchlistService（自选池）

```python
# vnpy_ashare/services/watchlist_service.py
# 职责：自选池 CRUD
# 聚合 app_db 操作 + bars.load_watchlist
# 方法：
#   get_items() → list[StockItem]
#   add(symbol, exchange, name) → bool
#   remove(symbol, exchange) → bool
#   move(symbol, exchange, direction) → bool
#   get_quotes() → dict (自选池实时行情)
```

#### 3.1.7 Engine 初始化变更

```python
# vnpy_ashare/engine.py (改造后)
class AshareEngine(BaseEngine):
    def __init__(self, main_engine, event_engine):
        super().__init__(main_engine, event_engine, APP_NAME)
        self.scheduler = TaskSchedulerManager()
        self.scheduler.start()
        # 新增
        self.bar_service = BarService(self)
        self.quote_service = QuoteService(self)
        self.backtest_service = BacktestService(self)
        self.screening_service = ScreeningService(self)
        self.watchlist_service = WatchlistService(self)

    def close(self):
        self.scheduler.shutdown()
        super().close()
```

---

### 3.2 Skills 层 — 按业务域拆分

#### 3.2.1 Skill 注入方案

`SkillEngine` 构造时接受 `services` 字典，在 `SkillTemplate.setup()` 时将 `self._services` 传递给实例：

```python
# vnpy_skills/engine.py (改造)
class SkillEngine:
    def __init__(self, skills_dir=None, services=None):
        ...
        self._services = services or {}

    def init_skills(self):
        for class_name, cls in sorted(self.classes.items()):
            instance = cls()
            instance._services = self._services  # 注入
            instance.on_init()
            ...
```

```python
# vnpy_llm/engine.py (改造)
class LlmEngine(BaseEngine):
    def __init__(self, main_engine, event_engine):
        ...
        ashare_engine = main_engine.get_engine("Ashare")
        services = {}
        if ashare_engine:
            services = {
                "bar": ashare_engine.bar_service,
                "quote": ashare_engine.quote_service,
                "backtest": ashare_engine.backtest_service,
                "screening": ashare_engine.screening_service,
                "watchlist": ashare_engine.watchlist_service,
            }
        self.skill_engine = SkillEngine(services=services)
        ...
```

#### 3.2.2 VnpyContextSkill（简化版）

- `get_quote_context()` — 当前选中标的与页面上下文
- `get_page_state()` — 当前所在页面

#### 3.2.3 VnpyDataSkill（新增）

- `get_bars_summary(symbol, scope)` — K 线概览
- `get_bars_data(symbol, scope, days)` — K 线 OHLCV 数据
- `get_quote(symbol)` — 实时行情
- `get_market_overview()` — 市场概览

#### 3.2.4 VnpyBacktestSkill（新增）

- `list_strategies()` — 可用策略列表
- `run_backtest(strategy, symbol, start, end, interval, capital)` — 触发回测
- `get_backtest_result()` — 最近回测结果
- `compare_strategies(strategies, symbol, start, end)` — 批量回测对比

#### 3.2.5 VnpyScreeningSkill（新增）

- `list_screeners()` — 可用选股条件
- `screen_by_condition(name, top_n)` — 选股
- `screen_custom(conditions)` — 组合条件选股

#### 3.2.6 VnpyWatchlistSkill（新增）

- `get_watchlist()` — 自选池列表
- `add_to_watchlist(symbol)` — 加入自选
- `remove_from_watchlist(symbol)` — 移出自选
- `get_watchlist_quotes()` — 自选池实时行情

---

### 3.3 AI 上下文优化

#### 3.3.1 分层知识注入

System Prompt 结构（改造后）：

```
1. 核心系统提示词（不变，~500 tokens）
2. 可用工具能力摘要（自动生成，~200 tokens）
3. Agent Skills 知识摘要（仅 name+description，每个 ~100 tokens）
4. 策略知识摘要（从 registry.py 提取，~300 tokens）
5. 当前终端上下文（选中标的/页面状态，~100 tokens）
```

`SkillEngine.build_skills_prompt()` 改为仅输出摘要，不再注入完整 SKILL.md body。LLM 需要详细知识时通过 `read_skill_file` 工具按需查阅。

#### 3.3.2 去掉 EVENT_AI_CONTEXT 事件广播

```
改造前：
QuotesPage._on_table_selection()
  → build_quote_context() 
  → event_engine.put(EVENT_AI_CONTEXT, data)
  → LlmEngine._on_context_event()
      → set_ai_context(data)  # 全局变量
      → signals.context_changed.emit()

改造后：
QuotesPage._on_table_selection()
  → ashare_engine.quote_service.set_current_selection(...)  # 一行 setter

Skill 调用时：
  → engine.quote_service.get_current_context()  # Lazy 读取
```

删除：`EVENT_AI_CONTEXT` 事件、`session_context.py` 中的全局变量、线程锁。

#### 3.3.3 策略知识暴露

从 `strategies/registry.py` 提取 `StrategyMeta`，在 System Prompt 中注入策略摘要：

```
【可用回测策略】
- 双均线策略：适用趋势明显的单边行情，不适用横盘震荡。
  参数：fast_window=5(快线周期), slow_window=20(慢线周期)
```

---

### 3.4 MCP — 保持不变

`vnpy_mcp` 模块设计合理，职责清晰，不需要大改。仅微调：

- MCP 工具调用加 30s 超时 + 错误提示
- 已在 LlmEngine 中正确集成，维持现状

---

### 3.5 体验优化

1. **工具错误提示增强** — 从 `{"error": "..."}` 改为人类可读提示 + 操作建议（如"请先在看盘页下载该标的日K数据"）
2. **对话上下文窗口管理** — ChatStore 加 message_count 上限（50条），工具调用结果超 2000 字符自动截断
3. **工具调用进度提示** — 耗时 > 3s 的工具调用显示进度提示

---

## 四、改动文件清单

### 新增（11 文件）

| 文件 | 说明 |
|------|------|
| `vnpy_ashare/services/__init__.py` | Service 导出 |
| `vnpy_ashare/services/base.py` | BaseService |
| `vnpy_ashare/services/bar_service.py` | K线数据服务 |
| `vnpy_ashare/services/quote_service.py` | 行情+上下文服务 |
| `vnpy_ashare/services/backtest_service.py` | 回测服务 |
| `vnpy_ashare/services/screening_service.py` | 选股服务 |
| `vnpy_ashare/services/watchlist_service.py` | 自选服务 |
| `skills/vnpy_data_skill.py` | 数据查询 Skill |
| `skills/vnpy_backtest_skill.py` | 回测 Skill |
| `skills/vnpy_screening_skill.py` | 选股 Skill |
| `skills/vnpy_watchlist_skill.py` | 自选管理 Skill |

### 修改（7 文件）

| 文件 | 改动 |
|------|------|
| `vnpy_ashare/engine.py` | 初始化 Services |
| `skills/vnpy_context_skill.py` | 简化，工具迁移到对应 Skill |
| `vnpy_skills/engine.py` | 支持 `services` 构造参数注入 |
| `vnpy_llm/engine.py` | 分层 prompt + 注入 services 到 SkillEngine |
| `vnpy_llm/prompts.py` | 策略知识注入模板 |
| `vnpy_ashare/ui/quotes_page.py` | `_emit_ai_context` 改为 setter 调用 |
| `vnpy_ashare/ui/backtest_widget.py` | `set_backtest_summary` 改为 backtest_service |

### 删除/简化

| 文件 | 说明 |
|------|------|
| `vnpy_llm/events.py` | 已移除 `EVENT_AI_CONTEXT`（保留其它 Event 兼容导出） |
| `vnpy_ashare/ai/session_context.py` | **已删除**；由 `context_store.py` + Service 替代 |

### 新增（相对设计稿）

| 文件 | 说明 |
|------|------|
| `vnpy_ashare/ai/context_store.py` | 线程安全内存存储（AI 上下文、回测/选股/诊断缓存） |
| `vnpy_ashare/config_bridge.py` | `.env` ↔ `vt_setting.json` 单源与漂移检测 |

### 不变

- `vnpy_mcp/` — 完整保留
- `vnpy_tickflow/` — 完整保留
- `vnpy_ashare/bar_store.py`、`bars.py`、`app_db.py` — 保留，由 Service 调用
- `vnpy_ashare/ai/context.py` — 保留
- `strategies/` — 保留
- `skills/tickflow/`、`skills/tushare-data/`（Agent Skills）— 保留
- `tests/` — 后续新增 Service/Skill 单测
- `docs/`、`scripts/` — 保留

---

## 五、实施顺序

| 阶段 | 状态 |
|------|------|
| P0 Service 层 | ✅ |
| P1 SkillEngine services 注入 | ✅ |
| P2 业务 Skill 拆分 | ✅ |
| P3 LlmEngine 分层 prompt | ✅ |
| P4 上下文优化（`context_store`、去掉 `session_context`） | ✅ |
| P5 体验优化（错误处理、进度提示等） | 部分 / 持续 |
| P6 Service + Skill 单测 | ✅（252 tests） |
