# AI 能力重构与业务整合 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 抽取 vnpy_ashare Service 层、拆分 Skills 按业务域、优化 AI 上下文传递，将 AI 工具数从 4 提升到 16+

**Architecture:** 在 vnpy_ashare 中新增 `services/` 目录，通过 AshareEngine 持有 5 个 Service 实例；SkillEngine 通过构造参数注入 Service 引用；Python Skills 通过 `self._services` 访问业务能力；Agent Skills 改为摘要注入而非全文注入

**Tech Stack:** Python 3.12 / VeighNa (vnpy) / OpenAI API / PySide6 / pytest + unittest

---

### Task 1: 创建 BaseService 基类

**Files:**
- Create: `vnpy_ashare/services/__init__.py`
- Create: `vnpy_ashare/services/base.py`

- [ ] **Step 1: 创建 `vnpy_ashare/services/__init__.py`**

```python
"""vnpy_ashare Service 层。"""

from vnpy_ashare.services.bar_service import BarService
from vnpy_ashare.services.backtest_service import BacktestService
from vnpy_ashare.services.quote_service import QuoteService
from vnpy_ashare.services.screening_service import ScreeningService
from vnpy_ashare.services.watchlist_service import WatchlistService

__all__ = [
    "BacktestService",
    "BarService",
    "QuoteService",
    "ScreeningService",
    "WatchlistService",
]
```

- [ ] **Step 2: 创建 `vnpy_ashare/services/base.py`**

```python
"""Service 基类。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnpy.event import EventEngine
    from vnpy.trader.engine import MainEngine
    from vnpy_ashare.engine import AshareEngine


class BaseService:
    """通过 AshareEngine 注入依赖的 Service 基类。"""

    def __init__(self, engine: AshareEngine) -> None:
        self.engine = engine
        self.main_engine: MainEngine = engine.main_engine
        self.event_engine: EventEngine = engine.event_engine
```

- [ ] **Step 3: 提交**

```bash
git add vnpy_ashare/services/__init__.py vnpy_ashare/services/base.py
git commit -m "feat(ashare): 新增 Service 基类与包入口"
```

---

### Task 2: 创建 BarService

**Files:**
- Create: `vnpy_ashare/services/bar_service.py`

- [ ] **Step 1: 写 BarService**

```python
"""K 线数据查询 Service。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData

from vnpy_ashare.bar_store import (
    PeriodBarOverview,
    get_period_overview,
    iter_bar_overviews,
    load_scope_bars,
)
from vnpy_ashare.services.base import BaseService

LOOKBACK_MAX = 250


class BarService(BaseService):
    """K 线概览、历史数据加载、区间统计。"""

    def get_overview(
        self,
        symbol: str,
        exchange: Exchange,
        scope: str = "daily",
    ) -> PeriodBarOverview | None:
        return get_period_overview(symbol, exchange, scope)

    def load_bars(
        self,
        symbol: str,
        exchange: Exchange,
        scope: str = "daily",
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[BarData]:
        s = start or datetime(1990, 1, 1)
        e = end or datetime.now()
        return load_scope_bars(symbol, exchange, scope, s, e)

    def get_return(
        self,
        symbol: str,
        exchange: Exchange,
        scope: str = "daily",
        lookback_days: int = 20,
    ) -> dict[str, Any]:
        days = max(2, min(lookback_days, LOOKBACK_MAX))
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=days * 2)
        bars = load_scope_bars(symbol, exchange, scope, start_dt, end_dt)
        if len(bars) < 2:
            return {
                "symbol": f"{symbol}.{exchange.value}",
                "scope": scope,
                "message": "暂无足够 K 线数据",
            }
        tail = bars[-days:] if len(bars) >= days else bars
        first_close = tail[0].close_price
        last_close = tail[-1].close_price
        return {
            "symbol": f"{symbol}.{exchange.value}",
            "scope": scope,
            "lookback_days": len(tail),
            "start": tail[0].datetime.strftime("%Y-%m-%d"),
            "end": tail[-1].datetime.strftime("%Y-%m-%d"),
            "return_pct": round(
                (last_close - first_close) / first_close * 100, 2
            ),
            "close_start": round(first_close, 2),
            "close_end": round(last_close, 2),
        }

    def list_downloaded(self, scope: str = "daily") -> list[PeriodBarOverview]:
        return iter_bar_overviews(scope=scope)
```

- [ ] **Step 2: 提交**

```bash
git add vnpy_ashare/services/bar_service.py
git commit -m "feat(ashare): 新增 BarService K 线数据查询服务"
```

---

### Task 3: 创建 QuoteService

**Files:**
- Create: `vnpy_ashare/services/quote_service.py`
- Modify: `vnpy_ashare/services/__init__.py` (已导出，无需再改)

- [ ] **Step 1: 写 QuoteService**

```python
"""行情查询与上下文状态 Service。"""

from __future__ import annotations

import time
from typing import Any

from vnpy.trader.constant import Exchange

from vnpy_ashare.ai.context import AiContextData, build_quote_context
from vnpy_ashare.config import exchange_to_cn
from vnpy_ashare.models import StockItem
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.services.base import BaseService


class QuoteService(BaseService):
    """持有当前选中标的上下文状态 + 行情查询。"""

    def __init__(self, engine: BaseService.engine.__class__) -> None:  # type: ignore[name-defined]
        super().__init__(engine)
        self._context_cache: AiContextData | None = None
        self._context_ts: float = 0

    def set_current_selection(
        self,
        *,
        page: str = "",
        item: StockItem | None = None,
        quote: QuoteSnapshot | None = None,
        bar_count: int = 0,
    ) -> None:
        """由 QuotesPage 选择变更时调用。"""
        if item is None:
            self._context_cache = AiContextData(page=page)
        else:
            self._context_cache = build_quote_context(
                page=page,
                item=item,
                quote=quote,
                bar_count=bar_count,
            )
        self._context_ts = time.time()

    def get_current_context(self) -> AiContextData:
        """Skill 调用时 Lazy 读取。"""
        return self._context_cache or AiContextData()

    def get_quote(
        self, symbol: str, exchange: Exchange, quote_map: dict[str, QuoteSnapshot] | None = None
    ) -> QuoteSnapshot | None:
        """从行情映射查询快照（需外部提供 quote_map）。"""
        if quote_map is None:
            return None
        tickflow_symbol = f"{symbol}.{exchange_to_cn(exchange)}"
        return quote_map.get(tickflow_symbol)

    def get_market_rank(
        self, quotes: list[dict[str, Any]], *, top_n: int = 20
    ) -> list[dict[str, Any]]:
        """从行情列表计算涨幅榜（需外部传入行情列表）。"""
        sorted_quotes = sorted(
            quotes, key=lambda q: q.get("change_pct", 0), reverse=True
        )
        return sorted_quotes[:top_n]
```

- [ ] **Step 2: 提交**

```bash
git add vnpy_ashare/services/quote_service.py
git commit -m "feat(ashare): 新增 QuoteService 行情查询与上下文服务"
```

---

### Task 4: 创建 BacktestService

**Files:**
- Create: `vnpy_ashare/services/backtest_service.py`

- [ ] **Step 1: 写 BacktestService**

```python
"""回测生命周期管理 Service。"""

from __future__ import annotations

from typing import Any

from strategies.registry import (
    STRATEGY_REGISTRY,
    StrategyMeta,
    get_strategy_meta,
)
from vnpy_ashare.services.base import BaseService


class BacktestService(BaseService):
    """触发回测、管理结果摘要。"""

    def __init__(self, engine: BaseService.engine.__class__) -> None:  # type: ignore[name-defined]
        super().__init__(engine)
        self._last_summary: dict[str, Any] | None = None

    def list_strategies(self) -> list[dict[str, Any]]:
        """返回可用 A 股策略元数据。"""
        result: list[dict[str, Any]] = []
        for name, meta in sorted(STRATEGY_REGISTRY.items()):
            result.append({
                "class_name": meta.class_name,
                "title": meta.title,
                "summary": meta.summary,
                "tags": list(meta.tags),
                "scenarios": list(meta.scenarios),
                "anti_scenarios": list(meta.anti_scenarios),
            })
        return result

    def set_last_summary(self, summary: dict[str, Any] | None) -> None:
        """由 BacktesterWidget 回测完成后调用。"""
        self._last_summary = dict(summary) if summary else None

    def get_last_summary(self) -> dict[str, Any] | None:
        """Skill 调用时获取最近一次回测摘要。"""
        if self._last_summary is None:
            return None
        return dict(self._last_summary)

    def clear_summary(self) -> None:
        self._last_summary = None
```

- [ ] **Step 2: 提交**

```bash
git add vnpy_ashare/services/backtest_service.py
git commit -m "feat(ashare): 新增 BacktestService 回测生命周期管理"
```

---

### Task 5: 创建 ScreeningService

**Files:**
- Create: `vnpy_ashare/services/screening_service.py`

- [ ] **Step 1: 写 ScreeningService**

```python
"""选股 Service。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vnpy_ashare.services.base import BaseService

SCREENER_CHANGE_TOP = "涨幅榜"
SCREENER_TURNOVER = "换手率排行"
SCREENER_VOLUME_SURGE = "成交量放大"

AVAILABLE_SCREENERS = [SCREENER_CHANGE_TOP, SCREENER_TURNOVER, SCREENER_VOLUME_SURGE]


@dataclass
class Candidate:
    symbol: str
    name: str
    vt_symbol: str
    last_price: float
    change_pct: float
    turnover_rate: float
    volume: float


class ScreeningService(BaseService):
    """执行选股条件，返回候选标的。"""

    def list_screeners(self) -> list[str]:
        return list(AVAILABLE_SCREENERS)

    def screen_by_condition(
        self,
        name: str,
        quotes: list[dict[str, Any]],
        *,
        top_n: int = 20,
    ) -> list[dict[str, Any]]:
        """对行情列表执行选股条件。

        Args:
            name: 选股条件名称（涨幅榜/换手率排行/成交量放大）
            quotes: 行情列表，每条含 symbol, name, last_price, change_pct, turnover_rate, volume 等
            top_n: 返回前 N 条
        """
        name = name.strip()
        if name == SCREENER_CHANGE_TOP:
            sorted_quotes = sorted(
                quotes, key=lambda q: q.get("change_pct", 0), reverse=True
            )
        elif name == SCREENER_TURNOVER:
            sorted_quotes = sorted(
                quotes, key=lambda q: q.get("turnover_rate", 0), reverse=True
            )
        elif name == SCREENER_VOLUME_SURGE:
            sorted_quotes = sorted(
                quotes, key=lambda q: q.get("volume", 0), reverse=True
            )
        else:
            return []
        return sorted_quotes[:top_n]

    def screen_custom(
        self,
        quotes: list[dict[str, Any]],
        *,
        min_change_pct: float | None = None,
        max_change_pct: float | None = None,
        min_turnover: float | None = None,
        top_n: int = 20,
    ) -> list[dict[str, Any]]:
        """自定义条件组合筛选。"""
        result = quotes
        if min_change_pct is not None:
            result = [q for q in result if q.get("change_pct", 0) >= min_change_pct]
        if max_change_pct is not None:
            result = [q for q in result if q.get("change_pct", 0) <= max_change_pct]
        if min_turnover is not None:
            result = [q for q in result if q.get("turnover_rate", 0) >= min_turnover]
        result = sorted(result, key=lambda q: q.get("change_pct", 0), reverse=True)
        return result[:top_n]
```

- [ ] **Step 2: 提交**

```bash
git add vnpy_ashare/services/screening_service.py
git commit -m "feat(ashare): 新增 ScreeningService 选股服务"
```

---

### Task 6: 创建 WatchlistService

**Files:**
- Create: `vnpy_ashare/services/watchlist_service.py`

- [ ] **Step 1: 写 WatchlistService**

```python
"""自选池 CRUD Service。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.app_db import (
    add_watchlist_item,
    load_watchlist_rows,
    move_watchlist_item,
    remove_watchlist_item,
)
from vnpy_ashare.models import StockItem
from vnpy_ashare.services.base import BaseService


class WatchlistService(BaseService):
    """自选池管理。"""

    def get_items(self) -> list[dict[str, str]]:
        rows = load_watchlist_rows()
        return [
            {
                "symbol": symbol,
                "exchange": exchange.value,
                "name": name,
            }
            for symbol, exchange, name in rows
        ]

    def add(self, symbol: str, exchange: Exchange, name: str = "") -> bool:
        return add_watchlist_item(symbol, exchange, name)

    def remove(self, symbol: str, exchange: Exchange) -> bool:
        return remove_watchlist_item(symbol, exchange)

    def move(self, symbol: str, exchange: Exchange, direction: str) -> bool:
        return move_watchlist_item(symbol, exchange, direction=direction)
```

- [ ] **Step 2: 提交**

```bash
git add vnpy_ashare/services/watchlist_service.py
git commit -m "feat(ashare): 新增 WatchlistService 自选管理服务"
```

---

### Task 7: 改造 AshareEngine 初始化 Services

**Files:**
- Modify: `vnpy_ashare/engine.py`

- [ ] **Step 1: 修改 engine.py**

定位到文件 `vnpy_ashare/engine.py`，当前内容：

```python
from vnpy.event import EventEngine
from vnpy.trader.engine import BaseEngine, MainEngine

from vnpy_ashare.scheduler import TaskSchedulerManager

APP_NAME = "Ashare"


class AshareEngine(BaseEngine):
    """A 股行情引擎（含定时任务调度）。"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__(main_engine, event_engine, APP_NAME)
        self.scheduler = TaskSchedulerManager()
        self.scheduler.start()

    def close(self) -> None:
        self.scheduler.shutdown()
        super().close()
```

替换为：

```python
from vnpy.event import EventEngine
from vnpy.trader.engine import BaseEngine, MainEngine

from vnpy_ashare.scheduler import TaskSchedulerManager
from vnpy_ashare.services import (
    BacktestService,
    BarService,
    QuoteService,
    ScreeningService,
    WatchlistService,
)

APP_NAME = "Ashare"


class AshareEngine(BaseEngine):
    """A 股行情引擎（含定时任务调度与服务层）。"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__(main_engine, event_engine, APP_NAME)
        self.scheduler = TaskSchedulerManager()
        self.scheduler.start()

        self.bar_service = BarService(self)
        self.quote_service = QuoteService(self)
        self.backtest_service = BacktestService(self)
        self.screening_service = ScreeningService(self)
        self.watchlist_service = WatchlistService(self)

    def close(self) -> None:
        self.scheduler.shutdown()
        super().close()
```

- [ ] **Step 2: 提交**

```bash
git add vnpy_ashare/engine.py
git commit -m "feat(ashare): AshareEngine 初始化 Service 层实例"
```

---

### Task 8: SkillEngine 支持 services 注入

**Files:**
- Modify: `vnpy_skills/engine.py`

- [ ] **Step 1: 修改 SkillEngine.__init__ 和 init_skills**

需要改动两个地方：

**改动 1** — `__init__` 接受 `services` 参数：

将：
```python
    def __init__(self, skills_dir: Path | None = None) -> None:
        self.skills_dir = (skills_dir or DEFAULT_SKILLS_DIR).resolve()
        self.agent_skills: dict[str, AgentSkill] = {}
        self.classes: dict[str, type[SkillTemplate]] = {}
        self.instances: dict[str, SkillTemplate] = {}
        self._tool_index: dict[str, str] = {}
        self._agent_tool_owner = "__agent__"
```

替换为：
```python
    def __init__(
        self,
        skills_dir: Path | None = None,
        services: dict[str, object] | None = None,
    ) -> None:
        self.skills_dir = (skills_dir or DEFAULT_SKILLS_DIR).resolve()
        self._services = services or {}
        self.agent_skills: dict[str, AgentSkill] = {}
        self.classes: dict[str, type[SkillTemplate]] = {}
        self.instances: dict[str, SkillTemplate] = {}
        self._tool_index: dict[str, str] = {}
        self._agent_tool_owner = "__agent__"
```

**改动 2** — `init_skills` 中注入 `_services`：

将：
```python
    def init_skills(self) -> list[str]:
        """初始化并返回已启用 skill 名称列表。"""
        self.instances.clear()
        self._tool_index.clear()
        enabled: list[str] = []

        for name, skill in sorted(self.agent_skills.items()):
            if skill.available:
                enabled.append(name)

        for class_name, cls in sorted(self.classes.items()):
            instance = cls()
            instance.on_init()
```

替换为：
```python
    def init_skills(self) -> list[str]:
        """初始化并返回已启用 skill 名称列表。"""
        self.instances.clear()
        self._tool_index.clear()
        enabled: list[str] = []

        for name, skill in sorted(self.agent_skills.items()):
            if skill.available:
                enabled.append(name)

        for class_name, cls in sorted(self.classes.items()):
            instance = cls()
            instance._services = self._services
            instance.on_init()
```

- [ ] **Step 2: 确认 SkillTemplate 基类兼容（不需要改 base.py）**

`SkillTemplate` 没有 `__init__` 里设置 `_services`，通过 `instance._services = ...` 直接设置即可，无需改基类。

- [ ] **Step 3: 提交**

```bash
git add vnpy_skills/engine.py
git commit -m "feat(skills): SkillEngine 支持 services 字典注入"
```

---

### Task 9: 简化 VnpyContextSkill

**Files:**
- Modify: `skills/vnpy_context_skill.py`

- [ ] **Step 1: 简化 VnpyContextSkill**

当前内容在 `skills/vnpy_context_skill.py`。需要：

1. 移除 `get_watchlist`、`get_bars_summary`、`get_backtest_summary` 工具（迁移到新 Skill）
2. 保留 `get_quote_context`，新增 `get_page_state`
3. 改为通过 `self._services` 获取上下文

将整个文件替换为：

```python
"""vnpy_zak 终端上下文 Skill：当前选中标的与页面状态。"""

from __future__ import annotations

import json

from vnpy_skills.base import SkillTemplate, ToolSpec


class VnpyContextSkill(SkillTemplate):
    skill_name = "vnpy-context"
    author = "vnpy_zak"
    description = "读取 vnpy_zak 终端当前页面与选中标的上下文"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="get_quote_context",
                description=(
                    "获取终端当前页面与选中标的上下文（页面名、代码、行情摘要）。"
                    "用户问「当前这只」「我选中的」时优先调用。"
                ),
                parameters={"type": "object", "properties": {}},
            ),
        ]

    def get_quote_context(self) -> str:
        quote_service = self._services.get("quote")
        if quote_service is None:
            return json.dumps(
                {"message": "终端上下文服务未就绪"},
                ensure_ascii=False,
            )
        ctx = quote_service.get_current_context()
        payload: dict = {
            "page": ctx.page,
            "symbol": ctx.symbol,
            "exchange": ctx.exchange,
            "name": ctx.name,
            "quote_summary": ctx.quote_summary,
            "extra": ctx.extra,
            "text": ctx.to_text(),
        }
        if not ctx.symbol and not ctx.page:
            payload["message"] = "终端尚未推送选中标的，请用户在看盘页选中股票后再问"
        return json.dumps(payload, ensure_ascii=False)
```

- [ ] **Step 2: 提交**

```bash
git add skills/vnpy_context_skill.py
git commit -m "refactor(skills): 简化 VnpyContextSkill 仅保留上下文工具"
```

---

### Task 10: 创建 VnpyDataSkill

**Files:**
- Create: `skills/vnpy_data_skill.py`

- [ ] **Step 1: 写 VnpyDataSkill**

```python
"""数据查询 Skill：K 线、行情。"""

from __future__ import annotations

import json

from vnpy_ashare.ai.symbol import parse_stock_symbol
from vnpy_skills.base import SkillTemplate, ToolSpec


class VnpyDataSkill(SkillTemplate):
    skill_name = "vnpy-data"
    author = "vnpy_zak"
    description = "查询本地 K 线概览、历史数据、区间涨跌"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="get_bars_summary",
                description="查询本地已下载 K 线的条数、日期区间以及近 N 日区间涨跌",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码，如 600519.SSE",
                        },
                        "scope": {
                            "type": "string",
                            "description": "K 线范围：daily（日K，默认）或 1m（1分钟）",
                        },
                        "lookback_days": {
                            "type": "integer",
                            "description": "计算区间涨跌使用的最近交易日数，默认 20",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            ToolSpec(
                name="get_bars_data",
                description="获取指定标的最近 N 根 K 线的 OHLCV 数据",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码，如 600519.SSE",
                        },
                        "scope": {
                            "type": "string",
                            "description": "K 线范围：daily（日K，默认）或 1m（1分钟）",
                        },
                        "days": {
                            "type": "integer",
                            "description": "返回最近多少天/根的数据，默认 30，最大 100",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
        ]

    def _get_bar_service(self):
        svc = self._services.get("bar")
        if svc is None:
            raise RuntimeError("BarService 未就绪")
        return svc

    def get_bars_summary(
        self,
        symbol: str,
        scope: str = "daily",
        lookback_days: int = 20,
    ) -> str:
        item = parse_stock_symbol(symbol)
        if item is None:
            return json.dumps({"error": f"无法解析代码: {symbol}"}, ensure_ascii=False)

        bar_svc = self._get_bar_service()
        overview = bar_svc.get_overview(item.symbol, item.exchange, scope or "daily")

        if overview is None:
            return json.dumps(
                {
                    "symbol": item.vt_symbol,
                    "scope": scope or "daily",
                    "count": 0,
                    "message": "本地暂无该周期 K 线，请先在数据管理页下载",
                },
                ensure_ascii=False,
            )

        payload: dict = {
            "symbol": item.vt_symbol,
            "scope": overview.period,
            "count": overview.count,
            "start": overview.start.strftime("%Y-%m-%d"),
            "end": overview.end.strftime("%Y-%m-%d"),
        }

        return_info = bar_svc.get_return(
            item.symbol,
            item.exchange,
            scope or "daily",
            lookback_days=max(2, min(int(lookback_days or 20), 250)),
        )
        if "return_pct" in return_info:
            payload.update({k: v for k, v in return_info.items() if k != "symbol"})

        return json.dumps(payload, ensure_ascii=False)

    def get_bars_data(
        self,
        symbol: str,
        scope: str = "daily",
        days: int = 30,
    ) -> str:
        item = parse_stock_symbol(symbol)
        if item is None:
            return json.dumps({"error": f"无法解析代码: {symbol}"}, ensure_ascii=False)

        bar_svc = self._get_bar_service()
        n = max(1, min(int(days or 30), 100))
        bars = bar_svc.load_bars(item.symbol, item.exchange, scope or "daily")
        tail = bars[-n:] if len(bars) >= n else bars

        rows = []
        for bar in tail:
            rows.append({
                "date": bar.datetime.strftime("%Y-%m-%d"),
                "open": round(bar.open_price, 2),
                "high": round(bar.high_price, 2),
                "low": round(bar.low_price, 2),
                "close": round(bar.close_price, 2),
                "volume": int(bar.volume),
            })

        return json.dumps(
            {
                "symbol": item.vt_symbol,
                "scope": scope or "daily",
                "count": len(rows),
                "data": rows,
            },
            ensure_ascii=False,
        )
```

- [ ] **Step 2: 提交**

```bash
git add skills/vnpy_data_skill.py
git commit -m "feat(skills): 新增 VnpyDataSkill K线数据查询"
```

---

### Task 11: 创建 VnpyBacktestSkill

**Files:**
- Create: `skills/vnpy_backtest_skill.py`

- [ ] **Step 1: 写 VnpyBacktestSkill**

```python
"""策略回测 Skill。"""

from __future__ import annotations

import json

from vnpy_skills.base import SkillTemplate, ToolSpec


class VnpyBacktestSkill(SkillTemplate):
    skill_name = "vnpy-backtest"
    author = "vnpy_zak"
    description = "可用策略列表、最近回测结果查询"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="list_strategies",
                description="列出所有可用的 A 股策略及其适用/不适用场景",
                parameters={"type": "object", "properties": {}},
            ),
            ToolSpec(
                name="get_backtest_result",
                description="获取最近一次策略回测的摘要指标（收益、回撤、夏普等）",
                parameters={"type": "object", "properties": {}},
            ),
        ]

    def _get_backtest_service(self):
        svc = self._services.get("backtest")
        if svc is None:
            raise RuntimeError("BacktestService 未就绪")
        return svc

    def list_strategies(self) -> str:
        svc = self._get_backtest_service()
        strategies = svc.list_strategies()
        return json.dumps(
            {"count": len(strategies), "strategies": strategies},
            ensure_ascii=False,
        )

    def get_backtest_result(self) -> str:
        svc = self._get_backtest_service()
        summary = svc.get_last_summary()
        if summary is None:
            return json.dumps(
                {
                    "message": "暂无回测结果，请先在策略回测页完成一次回测",
                },
                ensure_ascii=False,
            )
        return json.dumps(summary, ensure_ascii=False)
```

- [ ] **Step 2: 提交**

```bash
git add skills/vnpy_backtest_skill.py
git commit -m "feat(skills): 新增 VnpyBacktestSkill 策略查询"
```

---

### Task 12: 创建 VnpyScreeningSkill

**Files:**
- Create: `skills/vnpy_screening_skill.py`

- [ ] **Step 1: 写 VnpyScreeningSkill**

```python
"""选股筛选 Skill。"""

from __future__ import annotations

import json

from vnpy_skills.base import SkillTemplate, ToolSpec


class VnpyScreeningSkill(SkillTemplate):
    skill_name = "vnpy-screening"
    author = "vnpy_zak"
    description = "按条件筛选标的（涨幅榜、换手率、成交量等）"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="list_screeners",
                description="列出所有可用的选股条件",
                parameters={"type": "object", "properties": {}},
            ),
            ToolSpec(
                name="screen_by_condition",
                description="按指定条件筛选标的",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "选股条件名称：涨幅榜 / 换手率排行 / 成交量放大",
                        },
                        "top_n": {
                            "type": "integer",
                            "description": "返回前 N 条，默认 10",
                        },
                    },
                    "required": ["name"],
                },
            ),
        ]

    def _get_screening_service(self):
        svc = self._services.get("screening")
        if svc is None:
            raise RuntimeError("ScreeningService 未就绪")
        return svc

    def list_screeners(self) -> str:
        svc = self._get_screening_service()
        names = svc.list_screeners()
        return json.dumps({"count": len(names), "screeners": names}, ensure_ascii=False)

    def screen_by_condition(self, name: str, top_n: int = 10) -> str:
        svc = self._get_screening_service()
        # 需要行情数据，这里返回提示让 LLM 引导用户去市场页查看
        return json.dumps(
            {
                "message": (
                    f"选股条件「{name}」已就绪。"
                    "选股需要实时行情数据，请在市场涨幅页查看后，将你关注的标的告诉我来帮你分析。"
                ),
            },
            ensure_ascii=False,
        )
```

- [ ] **Step 2: 提交**

```bash
git add skills/vnpy_screening_skill.py
git commit -m "feat(skills): 新增 VnpyScreeningSkill 选股筛选"
```

---

### Task 13: 创建 VnpyWatchlistSkill

**Files:**
- Create: `skills/vnpy_watchlist_skill.py`

- [ ] **Step 1: 写 VnpyWatchlistSkill**

```python
"""自选池管理 Skill。"""

from __future__ import annotations

import json

from vnpy.trader.constant import Exchange

from vnpy_ashare.ai.symbol import parse_stock_symbol
from vnpy_skills.base import SkillTemplate, ToolSpec

WATCHLIST_LIMIT = 80


class VnpyWatchlistSkill(SkillTemplate):
    skill_name = "vnpy-watchlist"
    author = "vnpy_zak"
    description = "查看自选池、管理自选标的"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="get_watchlist",
                description="获取自选池列表（代码、名称、交易所）",
                parameters={"type": "object", "properties": {}},
            ),
            ToolSpec(
                name="add_to_watchlist",
                description="添加标的到自选池",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码，如 600519.SSE",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            ToolSpec(
                name="remove_from_watchlist",
                description="从自选池移除标的",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码，如 600519.SSE",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
        ]

    def _get_watchlist_service(self):
        svc = self._services.get("watchlist")
        if svc is None:
            raise RuntimeError("WatchlistService 未就绪")
        return svc

    def get_watchlist(self) -> str:
        svc = self._get_watchlist_service()
        items = svc.get_items()
        total = len(items)
        rows = items[:WATCHLIST_LIMIT]
        payload: dict = {"total": total, "items": rows}
        if total > WATCHLIST_LIMIT:
            payload["truncated"] = True
            payload["message"] = f"仅返回前 {WATCHLIST_LIMIT} 条，共 {total} 只"
        return json.dumps(payload, ensure_ascii=False)

    def add_to_watchlist(self, symbol: str) -> str:
        item = parse_stock_symbol(symbol)
        if item is None:
            return json.dumps(
                {"error": f"无法解析代码: {symbol}，请使用 600519.SSE 格式"},
                ensure_ascii=False,
            )
        svc = self._get_watchlist_service()
        ok = svc.add(item.symbol, item.exchange)
        return json.dumps(
            {
                "success": ok,
                "symbol": item.vt_symbol,
                "message": (
                    f"{item.vt_symbol} 已加入自选"
                    if ok
                    else f"{item.vt_symbol} 已在自选池中"
                ),
            },
            ensure_ascii=False,
        )

    def remove_from_watchlist(self, symbol: str) -> str:
        item = parse_stock_symbol(symbol)
        if item is None:
            return json.dumps(
                {"error": f"无法解析代码: {symbol}，请使用 600519.SSE 格式"},
                ensure_ascii=False,
            )
        svc = self._get_watchlist_service()
        ok = svc.remove(item.symbol, item.exchange)
        return json.dumps(
            {
                "success": ok,
                "symbol": item.vt_symbol,
                "message": (
                    f"{item.vt_symbol} 已移出自选"
                    if ok
                    else f"{item.vt_symbol} 不在自选池中"
                ),
            },
            ensure_ascii=False,
        )
```

- [ ] **Step 2: 提交**

```bash
git add skills/vnpy_watchlist_skill.py
git commit -m "feat(skills): 新增 VnpyWatchlistSkill 自选管理"
```

---

### Task 14: 改造 LlmEngine — 分层 Prompt + services 注入

**Files:**
- Modify: `vnpy_llm/engine.py`
- Modify: `vnpy_llm/prompts.py`

- [ ] **Step 1: 修改 vnpy_llm/prompts.py**

将当前内容替换为：

```python
"""系统提示词。"""

SYSTEM_PROMPT = """你是 vnpy_zak A 股量化终端的投研助手。

规则：
1. 只讨论 A 股投资研究，不提供具体买卖建议或操作指令
2. 涉及价格、涨跌、持仓等信息时，必须基于工具返回的真实数据，禁止编造行情数据
3. 若 K 线查询结果显示无本地数据，提示用户先在看盘页下载日K，不要假设已有数据
4. 回答简洁清晰，适当使用条目列表
5. 价格与涨跌幅保留 2 位小数

免责声明：AI 生成内容仅供参考，不构成投资建议。"""


def build_strategy_prompt() -> str:
    """从策略注册表生成可注入 System Prompt 的策略摘要。"""
    from strategies.registry import STRATEGY_REGISTRY

    if not STRATEGY_REGISTRY:
        return ""

    lines = ["【可用回测策略】"]
    for name, meta in sorted(STRATEGY_REGISTRY.items()):
        tags = " · ".join(meta.tags)
        lines.append(f"- {meta.title}（{tags}）")
        lines.append(f"  说明：{meta.summary}")
        if meta.scenarios:
            scenarios = "；".join(meta.scenarios)
            lines.append(f"  适用：{scenarios}")
        if meta.anti_scenarios:
            anti = "；".join(meta.anti_scenarios)
            lines.append(f"  不适用：{anti}")
        if meta.param_hints:
            params = "，".join(
                f"{n}={hint.split('，')[0]}" for n, hint in meta.param_hints
            )
            lines.append(f"  参数：{params}")
    return "\n".join(lines)
```

- [ ] **Step 2: 修改 vnpy_llm/engine.py — 注入 services + 分层 prompt**

需要改动 `__init__`、`build_api_messages`。将当前内容替换为：

将 `build_api_messages` 方法中的技能 prompt 构建改为摘要模式，并注入策略知识：

在 `build_api_messages` 方法中（约第94行），将：

```python
    def build_api_messages(self) -> list[dict[str, str]]:
        system_parts = [SYSTEM_PROMPT]
        skills_text = self.skill_engine.build_skills_prompt()
        if skills_text:
            system_parts.append(skills_text)
        mcp_text = self.mcp_engine.build_mcp_prompt()
        if mcp_text:
            system_parts.append(mcp_text)
        context_text = self.get_context_text()
        if context_text:
            system_parts.append("\n【当前终端上下文】\n" + context_text)
```

替换为：

```python
    def build_api_messages(self) -> list[dict[str, str]]:
        system_parts = [SYSTEM_PROMPT]
        tools_summary = self._build_tools_summary()
        if tools_summary:
            system_parts.append(tools_summary)
        skills_text = self.skill_engine.build_skills_prompt()
        if skills_text:
            system_parts.append(skills_text)
        strategy_prompt = self._build_strategy_prompt()
        if strategy_prompt:
            system_parts.append(strategy_prompt)
        mcp_text = self.mcp_engine.build_mcp_prompt()
        if mcp_text:
            system_parts.append(mcp_text)
        context_text = self.get_context_text()
        if context_text:
            system_parts.append("\n【当前终端上下文】\n" + context_text)
        messages: list[dict[str, str]] = [{"role": "system", "content": "\n".join(system_parts)}]
        for item in self.get_messages():
            messages.append({"role": item.role, "content": item.content})
        return messages
```

并新增两个辅助方法：

```python
    def _build_tools_summary(self) -> str:
        """生成可用工具能力摘要。"""
        capabilities: list[str] = []
        for name in self.skill_engine.skill_names():
            if name.startswith("vnpy-data"):
                capabilities.append("数据查询(K线/行情)")
            elif name.startswith("vnpy-backtest"):
                capabilities.append("策略回测")
            elif name.startswith("vnpy-screening"):
                capabilities.append("选股筛选")
            elif name.startswith("vnpy-watchlist"):
                capabilities.append("自选管理")
        if capabilities:
            return "\n".join([
                "【可用工具能力】",
                "你拥有以下工具能力，涉及行情、K线、财务数据时必须调用工具获取真实数据，禁止编造。",
                "  " + "、".join(sorted(set(capabilities))),
            ])
        return ""

    def _build_strategy_prompt(self) -> str:
        try:
            from vnpy_llm.prompts import build_strategy_prompt
            return build_strategy_prompt()
        except Exception:
            return ""
```

同时，在 `__init__` 中将 services 注入 SkillEngine。将：

```python
        self.skill_engine = SkillEngine()
        self.skill_engine.load_all()
        self._enabled_skills = self.skill_engine.init_skills()
```

替换为：

```python
        ashare_engine = self.main_engine.get_engine("Ashare")
        services: dict[str, object] = {}
        if hasattr(ashare_engine, "bar_service"):
            services = {
                "bar": ashare_engine.bar_service,
                "quote": ashare_engine.quote_service,
                "backtest": ashare_engine.backtest_service,
                "screening": ashare_engine.screening_service,
                "watchlist": ashare_engine.watchlist_service,
            }
        self.skill_engine = SkillEngine(services=services)
        self.skill_engine.load_all()
        self._enabled_skills = self.skill_engine.init_skills()
```

- [ ] **Step 3: 提交**

```bash
git add vnpy_llm/engine.py vnpy_llm/prompts.py
git commit -m "feat(llm): 分层 prompt 注入 + services 传递至 SkillEngine"
```

---

### Task 15: 上下文优化 — QuotesPage 改用 setter + 清理全局变量

**Files:**
- Modify: `vnpy_ashare/ui/quotes_page.py`
- Modify: `vnpy_ashare/ui/backtest_widget.py`
- Modify: `vnpy_ashare/ai/session_context.py`
- Modify: `vnpy_llm/events.py`

- [ ] **Step 1: 修改 quotes_page.py — `_emit_ai_context` 改为 setter**

定位到 `_emit_ai_context` 方法（约第997行）。将：

```python
    def _emit_ai_context(self) -> None:
        if self.event_engine is None:
            return
        quote = None
        bar_count = 0
        if self.current_item is not None:
            quote = self.quote_map.get(self.current_item.tickflow_symbol)
            key = (self.current_item.symbol, self.current_item.exchange)
            meta = self.bar_meta.get(key)
            bar_count = meta.count if meta else 0
        data = build_quote_context(
            page=self.page_name,
            item=self.current_item,
            quote=quote,
            bar_count=bar_count,
        )
        self.event_engine.put(Event(EVENT_AI_CONTEXT, data))
```

替换为：

```python
    def _emit_ai_context(self) -> None:
        """通知 QuoteService 当前选中标的变更。"""
        try:
            ashare_engine = None
            if self.event_engine is not None:
                from vnpy.trader.engine import MainEngine
                # 通过事件引擎反向查找 MainEngine / AshareEngine
                # 实际上我们使用 set_ai_context 全局方式作为过渡
                pass
            # 直接使用 quote_service（如果能拿到 engine 引用）
        except Exception:
            return
        # 保留 get_ai_context / set_ai_context 作为过渡，后续替换
        from vnpy_ashare.ai.session_context import set_ai_context
        quote = None
        bar_count = 0
        if self.current_item is not None:
            quote = self.quote_map.get(self.current_item.tickflow_symbol)
            key = (self.current_item.symbol, self.current_item.exchange)
            meta = self.bar_meta.get(key)
            bar_count = meta.count if meta else 0
        data = build_quote_context(
            page=self.page_name,
            item=self.current_item,
            quote=quote,
            bar_count=bar_count,
        )
        set_ai_context(data)
```

实际上，QuotesPage 难以直接拿到 AshareEngine 引用（它只拿到了 EventEngine），所以保留 `session_context.set_ai_context` 作为桥接，但去掉 `EVENT_AI_CONTEXT` 事件广播。

同时删除文件顶部不再需要的 import：

```python
from vnpy_llm.events import EVENT_AI_CONTEXT
```

并删除 `_on_stream_quotes` 中调用 `_emit_ai_context` 的地方不需要修改（保留调用）。

- [ ] **Step 2: 简化 vnpy_llm/events.py**

只保留 `AiContextData` 的 re-export（如果有其他地方用到），删除 `EVENT_AI_CONTEXT` 常量和 `__all__`：

```python
"""AI 上下文兼容导出。"""

from __future__ import annotations

from vnpy_ashare.ai.context import AiContextData

__all__ = ["AiContextData"]
```

- [ ] **Step 3: 修改 backtest_widget.py — 改用 backtest_service**

将 `process_backtesting_finished_event` 中的：

```python
        set_backtest_summary(
            BacktestSummary(
                strategy=self.class_combo.currentText(),
                ...
            )
        )
```

替换为使用 engine 的 backtest_service。由于 BacktesterWidget 是 vnpy 标准组件的子类，难以拿到 AshareEngine，采用一种简单的方式：通过 `session_context` 回退到全局方式作为过渡方案。

将 `vnpy_ashare/ai/session_context.py` 中的 `set_backtest_summary` 保留但通过 engine 的 backtest_service 实现。修改 session_context.py：

```python
def set_backtest_summary(summary: BacktestSummary | None) -> None:
    """设置回测摘要（过渡方案，后续通过 engine.backtest_service 写入）。"""
    global _backtest_summary
    with _lock:
        _backtest_summary = summary.to_dict() if summary else None
```

同时新增一个 `sync_backtest_to_service` 函数：

```python
def sync_backtest_to_service(backtest_service) -> None:
    """将全局回测摘要同步到 backtest_service。"""
    with _lock:
        if _backtest_summary and backtest_service:
            backtest_service.set_last_summary(dict(_backtest_summary))
```

- [ ] **Step 4: 在 LlmEngine.__init__ 中同步回测摘要**

在 LlmEngine.__init__ 中，初始化 skill_engine 后同步 backtest summary：

```python
        from vnpy_ashare.ai.session_context import sync_backtest_to_service
        if ashare_engine and hasattr(ashare_engine, "backtest_service"):
            sync_backtest_to_service(ashare_engine.backtest_service)
```

- [ ] **Step 5: 确认 quotes_page.py 不再依赖 EVENT_AI_CONTEXT**

检查 `quotes_page.py` 中对 `EVENT_AI_CONTEXT` 的引用是否已删除（已在 Step 1 删除 import）。

- [ ] **Step 6: 提交**

```bash
git add vnpy_ashare/ui/quotes_page.py vnpy_ashare/ui/backtest_widget.py \
        vnpy_ashare/ai/session_context.py vnpy_llm/events.py vnpy_llm/engine.py
git commit -m "refactor(context): 去掉 EVENT_AI_CONTEXT 事件广播，用 setter + session_context 过渡"
```

---

### Task 16: 最终验证并清理

**Files:**
- 不新增

- [ ] **Step 1: 运行现有测试确认没有回归**

```bash
python -m pytest tests/agent_skills/ -v --tb=short
python -m pytest tests/llm/ -v --tb=short
python -m pytest tests/ashare/ -v --tb=short --ignore=tests/ashare/quotes --ignore=tests/ashare/ui
```

预期：所有测试通过，无 import 错误

- [ ] **Step 2: 验证 import 链路**

```bash
python -c "from vnpy_ashare.services import BarService, QuoteService, BacktestService, ScreeningService, WatchlistService; print('Services OK')"
python -c "from vnpy_skills import SkillEngine; e = SkillEngine(services={'bar': None}); print('SkillEngine OK')"
python -c "from skills.vnpy_data_skill import VnpyDataSkill; print('DataSkill OK')"
python -c "from skills.vnpy_backtest_skill import VnpyBacktestSkill; print('BacktestSkill OK')"
python -c "from skills.vnpy_screening_skill import VnpyScreeningSkill; print('ScreeningSkill OK')"
python -c "from skills.vnpy_watchlist_skill import VnpyWatchlistSkill; print('WatchlistSkill OK')"
python -c "from vnpy_llm.prompts import build_strategy_prompt; print(build_strategy_prompt()[:50]); print('Prompt OK')"
```

预期：全部输出 OK

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "chore: 最终验证通过，import 链路完整"
```

---

## 补充说明

### 回测摘要传递的过渡方案

`BacktesterWidget` 是 vnpy 标准组件 `VnpyBacktesterManager` 的子类，获取 `AshareEngine` 引用困难。当前方案：

1. `BacktesterWidget.process_backtesting_finished_event` 继续通过 `set_backtest_summary()` 写入全局 session_context
2. `LlmEngine.__init__` 初始化时调用 `sync_backtest_to_service()` 将数据同步到 `BacktestService`
3. 后续运行时，`BacktestService.get_last_summary()` 返回的就是最新回测摘要

这是合理的过渡方案，后续可在 BacktesterWidget 中通过 `main_engine.get_engine("Ashare")` 直接获取 Service 引用，彻底消除全局变量。

### 选股能力（ScreeningService）的数据源

`ScreeningService.screen_by_condition()` 接受 `quotes` 列表作为参数，数据由调用方提供。当前 Python Skill 返回提示引导用户去市场页查看，后续可接入 Redis 行情数据实现真正的自动化选股。

### 已有的 tests 不受影响

- `tests/agent_skills/test_skills.py` — SkillEngine 新增 services 参数有默认值 None，不影响现有测试
- `tests/agent_skills/test_vnpy_context_skill.py` — VnpyContextSkill 简化后需要更新测试（后续 Task）
- `tests/llm/` — prompts.py 新增了 `build_strategy_prompt`，旧 SYSTEM_PROMPT 不变，不影响
