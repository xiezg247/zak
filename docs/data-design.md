# 数据设计

zak 使用 **类双存储结构**，元数据与行情数据分离：

- **元数据**：App DB + LLM Chat DB — 固定为本地 SQLite，不随 `DATABASE_NAME` 切换
- **K 线数据**：通过 VeighNa adapter 层，可选 SQLite 或 PostgreSQL（由 `DATABASE_NAME` / `database.name` 控制）

建表语句在代码中内联执行（`CREATE TABLE IF NOT EXISTS`），无独立迁移文件。终端 AI 共享态在 `context_store`（内存，非 DB）。

---

## 一、App DB：项目元数据

| 属性 | 值 |
|------|-----|
| 数据库文件 | `~/.vntrader/zak.db`（`APP_DB_PATH`） |
| ORM/方式 | 原生 `sqlite3` |
| 定义文件 | `vnpy_ashare/app_db.py` |
| 初始化入口 | `init_app_db()` |

### 1.1 `meta` — 键值元数据

```sql
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `key` | TEXT PK | 元数据键 |
| `value` | TEXT | 元数据值 |

**已有 key：**

- `universe_synced_at`：全 A 股列表最后同步时间（ISO 格式）

### 1.2 `watchlist` — 自选池

```sql
CREATE TABLE IF NOT EXISTS watchlist (
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (symbol, exchange)
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | TEXT PK | 证券代码（如 `600519`） |
| `exchange` | TEXT PK | 交易所（`SSE` / `SZSE` / `BSE`） |
| `name` | TEXT | 证券名称（如 `贵州茅台`） |
| `sort_order` | INTEGER | 排序权重（按加入先后），删除时自动收缩 |

**用途：** 用户自选股列表，支持新增、删除、排序（上移/下移）、CSV 导入导出。`sort_order` 在删除后会重新编号以保持连续。

### 1.3 `universe` — 全 A 股标的列表

```sql
CREATE TABLE IF NOT EXISTS universe (
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (symbol, exchange)
);

CREATE INDEX IF NOT EXISTS idx_universe_symbol ON universe(symbol);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | TEXT PK | 证券代码 |
| `exchange` | TEXT PK | 交易所 |
| `name` | TEXT | 证券名称 |

**用途：** 缓存 TickFlow `CN_Equity_A` 全市场约 5000+ 只 A 股标的列表。支持分页读取（`load_universe_page`）和模糊搜索（`search_universe`，匹配代码或名称）。缓存有效期 7 天（`CACHE_MAX_AGE = 7d`），通过 `universe_synced_at` meta 字段判断是否过期。

### 1.4 `trade_calendar` — 交易日历

```sql
CREATE TABLE IF NOT EXISTS trade_calendar (
    cal_date TEXT PRIMARY KEY,
    is_open INTEGER NOT NULL
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `cal_date` | TEXT PK | 日期（`YYYY-MM-DD` 格式） |
| `is_open` | INTEGER | 是否交易日（1=是, 0=否） |

**用途：** 从 Tushare Pro 同步 SSE 交易日历，用于 K 线断层检测（`bar_health.py`）和回测日期判断。

### 1.5 `backtest_runs` — 回测运行历史

定义文件：`vnpy_ashare/backtest/run_store.py`。写入：`BacktestService.persist_summary()`。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PK | UUID |
| `vt_symbol` | TEXT | 标的（如 `600519.SSE`） |
| `strategy` | TEXT | 策略类名 |
| `interval` | TEXT | K 线周期（默认 `d`） |
| `start_date` / `end_date` | TEXT | 回测区间 |
| `total_return` / `max_drawdown` / `sharpe_ratio` | REAL | 摘要指标 |
| `trade_count` | INTEGER | 成交笔数 |
| `source` | TEXT | `single` / `batch_screener` / `batch_watchlist` 等 |
| `batch_id` | TEXT | 批量回测批次 ID（可空） |
| `raw_statistics_json` | TEXT | vnpy 统计 JSON |
| `created_at` | TEXT | 写入时间 |

**用途：** AI 工具 `get_backtest_result` / `list_backtest_history` 与回测页「问 AI」读取；内存缓存同步至 `context_store`。

### 1.6 `screener_schemes` — 选股方案

定义文件：`vnpy_ashare/screener/preset/scheme_store.py`。用户保存的条件选股方案（preset + 自定义阈值 JSON）。

### 1.7 `screener_recipes` — 多因子配方

定义文件：`vnpy_ashare/screener/recipe/recipe_store.py`。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PK | UUID |
| `name` | TEXT UNIQUE | 配方名称 |
| `trigger_kind` | TEXT | `intraday` / `post_close` |
| `config_json` | TEXT | 维度权重、`top_n`、`pool_size` 等 |
| `created_at` / `updated_at` | TEXT | 时间戳 |

定时任务 `screen_intraday` 引用配方 ID 执行；AI `run_recipe` 可读内置或用户配方。

### 1.8 `screener_runs` — 选股运行历史

定义文件：`vnpy_ashare/screener/run/run_store.py`。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PK | UUID |
| `condition` | TEXT | 人类可读条件摘要 |
| `source` | TEXT | `condition` / `recipe` / `pattern` / `ai` 等 |
| `row_count` | INTEGER | 结果行数 |
| `total_scanned` | INTEGER | 扫描池大小 |
| `config_json` | TEXT | trigger、recipe_id、read_at 等元数据 |
| `result_json` | TEXT | 结果行 JSON 数组 |
| `created_at` | TEXT | 写入时间 |

**用途：** Hub 左侧收件箱、较上次 diff（`run_diff.py`）、`ScreeningService` → `context_store` → AI `get_screening_context`。

### 1.9 个股笔记与研报

定义文件：`vnpy_ashare/storage/connection.py`（与 watchlist 等同库）。

| 表 | 说明 |
|----|------|
| `stock_note_memos` | 每票一行备忘（upsert） |
| `stock_note_entries` | 每票多条流水（追加） |
| `stock_analysis_reports` | 分析报告；含 `source_scope`（如 `team_analysis`）、`context_json`（团队评分等） |

详见 [看盘页个股笔记](./stock-notes.md)。

### 1.10 `watchlist_groups` — 自选分组

定义文件：`vnpy_ashare/storage/repositories/watchlist_groups.py`（`connection.py` 建表）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PK | UUID |
| `name` | TEXT | 分组名（用户自定义，如「龙头」「题材」） |
| `sort_order` | INTEGER | Tab 顺序 |

关联表 `watchlist_group_members`：`(group_id, symbol, exchange)` PK，标的可属于多组；删除分组 CASCADE 成员。

**用途：** 自选页 Tab 切换（P-06 **已有**）；雷达/选股「加自选」写入自选池，分组仅作用户视图。详见 [自选分组](./watchlist-groups.md)。

### 1.11 交易计划与流水（**已有**）

> J-01、J-02 已落库。详见 [交易计划与流水](./trading-plan-journal.md)。

#### `trading_plans`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PK | UUID |
| `trade_date` | TEXT | 计划适用交易日 |
| `emotion_expected` | TEXT | 预期情绪阶段 |
| `max_position_pct` | REAL | 计划总仓位 0–100 |
| `notes` | TEXT | 备忘 |
| `status` | TEXT | `draft` / `active` / `archived` |
| `created_at` / `updated_at` | TEXT | 时间戳 |

#### `trading_plan_symbols`

| 字段 | 类型 | 说明 |
|------|------|------|
| `plan_id` | TEXT FK | → `trading_plans.id` |
| `symbol` / `exchange` | TEXT | 标的 |
| `allowed_modes_json` | TEXT | 打板 / 半路 / 低吸 |
| `entry_conditions_json` | TEXT | 结构化入场条件 |
| `exit_conditions_json` | TEXT | 结构化退出条件 |

#### `trade_journal`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PK | UUID |
| `symbol` / `exchange` | TEXT | 标的 |
| `trade_date` | TEXT | 交易日 |
| `side` | TEXT | `buy` / `sell` |
| `mode` | TEXT | `limit_board` / `halfway` / `pullback` 等 |
| `price` / `volume` | REAL / INTEGER | 成交价、数量 |
| `pnl_pct` | REAL | 盈亏 %（卖出行） |
| `off_plan` | INTEGER | 是否计划外（0/1） |
| `plan_id` | TEXT | 关联计划（可空） |
| `notes` | TEXT | 备注 |
| `created_at` | TEXT | 写入时间 |

**用途：** K-05 违规统计、J-05 复盘报表；与 `stock_note_entries` 并存（笔记偏定性，流水偏聚合）。

### 1.12 `notify_delivery_log`（**已有**，N-05）

> Phase 2 已落库。详见 [消息通知](./notifications.md)。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PK | UUID |
| `event_type` | TEXT | 如 `screener_intraday_done` |
| `channel` | TEXT | `feishu` |
| `payload_json` | TEXT | 发送内容摘要 |
| `status` | TEXT | `sent` / `failed` / `deduped` |
| `error` | TEXT | 失败原因 |
| `created_at` | TEXT | 时间戳 |

### 1.13 风控与交易配置（非 DB）

以下存 **QSettings** 或 `.env`，不落 App DB 表：

| 键 / 环境变量 | 说明 | 文档 |
|---------------|------|------|
| `trading/strategy_profile` | 策略 Profile | [strategy-profiles.md](./strategy-profiles.md) |
| `trading/total_capital` 等 | 总资金、单笔止损 % | [risk-gate.md](./risk-gate.md) |
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook | [notifications.md](./notifications.md) |
| `NOTIFY_*` | 通知开关与限频 | 同上 |
| `RECIPE_*` | 硬过滤 env 覆盖 | [intraday-screening.md](./intraday-screening.md) |

### 1.14 其它 App DB 表

| 表 | 说明 |
|----|------|
| `symbol_suspend_days` | Tushare 停牌日历，供硬过滤 |
| `watchlist_positions` | 自选持仓跟踪（与笔记独立） |

---

## 二、K 线 DB：市场数据（SQLite 或 PostgreSQL）

| 属性 | 值 |
|------|-----|
| **SQLite 模式** | `~/.vntrader/database.db`（默认，`DATABASE_NAME=sqlite`） |
| **PostgreSQL 模式** | 远程 PostgreSQL（`DATABASE_NAME=postgresql`，需 `.env` 配置 `POSTGRES_*`） |
| ORM/方式 | **Peewee ORM**（`vnpy_sqlite` 或 `vnpy_postgresql` adapter） |
| 本项目引用 | `vnpy_ashare/bar_store.py`、`vnpy_ashare/bars.py` |
| 切换方式 | 修改 `.env` 中 `DATABASE_NAME` → 设置页「从 .env 同步」→ 重启 GUI |

> 下表结构在 SQLite / PostgreSQL 中一致，由 Peewee ORM 自动处理方言差异。

### 2.1 `dbbardata` — K 线数据

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | AutoField PK | 自增主键 |
| `symbol` | CharField | 证券代码 |
| `exchange` | CharField | 交易所 |
| `datetime` | DateTimeField | K 线时间 |
| `interval` | CharField | 周期（`1m`、`1d` 等） |
| `volume` | FloatField | 成交量 |
| `turnover` | FloatField | 成交额 |
| `open_interest` | FloatField | 持仓量 |
| `open_price` | FloatField | 开盘价 |
| `high_price` | FloatField | 最高价 |
| `low_price` | FloatField | 最低价 |
| `close_price` | FloatField | 收盘价 |

- **唯一约束：** `(symbol, exchange, interval, datetime)`

### 2.2 `dbtickdata` — Tick 逐笔数据

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | AutoField PK | 自增主键 |
| `symbol` | CharField | 证券代码 |
| `exchange` | CharField | 交易所 |
| `datetime` | DateTimeField | Tick 时间 |
| `name` | CharField | 证券名称 |
| `volume` | FloatField | 成交量 |
| `turnover` | FloatField | 成交额 |
| `open_interest` | FloatField | 持仓量 |
| `last_price` | FloatField | 最新价 |
| `last_volume` | FloatField | 最新成交量 |
| `limit_up` | FloatField | 涨停价 |
| `limit_down` | FloatField | 跌停价 |
| `open_price` | FloatField | 开盘价 |
| `high_price` | FloatField | 最高价 |
| `low_price` | FloatField | 最低价 |
| `pre_close` | FloatField | 昨收价 |
| `bid_price_1~5` | FloatField | 五档买价 |
| `bid_volume_1~5` | FloatField | 五档买量 |
| `ask_price_1~5` | FloatField | 五档卖价 |
| `ask_volume_1~5` | FloatField | 五档卖量 |
| `localtime` | DateTimeField | 本地时间 |

- **唯一约束：** `(symbol, exchange, datetime)`

### 2.3 `dbbaroverview` — K 线概览

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | AutoField PK | 自增主键 |
| `symbol` | CharField | 证券代码 |
| `exchange` | CharField | 交易所 |
| `interval` | CharField | 周期 |
| `count` | IntegerField | K 线条数 |
| `start` | DateTimeField | 最早 K 线时间 |
| `end` | DateTimeField | 最晚 K 线时间 |

- **唯一约束：** `(symbol, exchange, interval)`

### 2.4 `dbtickoverview` — Tick 概览

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | AutoField PK | 自增主键 |
| `symbol` | CharField | 证券代码 |
| `exchange` | CharField | 交易所 |
| `count` | IntegerField | Tick 条数 |
| `start` | DateTimeField | 最早 Tick 时间 |
| `end` | DateTimeField | 最晚 Tick 时间 |

- **唯一约束：** `(symbol, exchange)`

---

## 三、LLM Chat DB：AI 聊天历史

| 属性 | 值 |
|------|-----|
| 数据库文件 | `~/.vntrader/llm_chat.db` |
| ORM/方式 | 原生 `sqlite3` |
| 定义文件 | `vnpy_llm/store.py` |
| 操作类 | `ChatStore` |

### 3.1 `sessions` — 聊天会话

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PK | UUID（`uuid4().hex` 生成） |
| `title` | TEXT | 会话标题（默认"默认会话"或"新会话"） |
| `created_at` | TEXT | 创建时间（`YYYY-MM-DD HH:MM:SS`） |
| `updated_at` | TEXT | 最后活跃时间 |

### 3.2 `messages` — 聊天消息

```sql
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增主键 |
| `session_id` | TEXT FK | 所属会话 |
| `role` | TEXT | 角色（`user` / `assistant` / `system`） |
| `content` | TEXT | 消息正文 |
| `created_at` | TEXT | 创建时间 |

**限制：**

- `MAX_MESSAGES_PER_SESSION = 50`：每个会话 `list_messages()` 最多取最近 50 条
- `MAX_TOOL_RESULT_CHARS = 2000`：写入 DB 前，tool_result 超过此长度的内容会被截断

多会话 UI：全屏页 `AiSessionSidebar`、Dock/悬浮「历史会话」弹窗；会话持久化于 `llm_chat.db`。

---

## 四、Redis 缓存层

| 属性 | 值 |
|------|-----|
| 定义文件 | `vnpy_ashare/quotes/core/redis_store.py` |
| 操作类 | `RedisQuoteStore` |
| 连接方式 | 支持单机 / 集群，从 `.env` 读取配置 |

### 4.1 行情快照

- **Key 模式：** `zak:quote:{symbol}`
- **类型：** HASH
- **字段：** `symbol`、`name`、`last_price`、`prev_close`、`open_price`、`high_price`、`low_price`、`change_amount`、`change_pct`、`turnover_rate`、`volume`、`amount`、`amplitude`、`trade_time`（共 14 个字段）
- **写入：** `write_quotes()` 批量 pipeline 写入

### 4.2 市场涨幅排名

- **Key：** `zak:rank:change_pct`
- **类型：** ZSET（有序集合）
- **Score：** 涨跌幅（`change_pct`）
- **Member：** `symbol`
- **读取：** `get_rank_symbols()` 按降序分页取

### 4.3 元信息

| Key | 类型 | 说明 |
|-----|------|------|
| `zak:meta:updated_at` | STRING | 行情最新更新时间（ISO 格式） |
| `zak:meta:quote_count` | STRING | 当前行情快照条数 |

### 4.4 配置

```env
# Redis 连接（以下按优先顺序）
REDIS_URL=redis://localhost:6379/0     # 完整 URL，比分散字段优先
REDIS_CLUSTER=false                    # 是否集群模式（仅 REDIS_URL 时生效）

# 分散字段（REDIS_URL 未设置时使用）
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
```

---

## 五、内存 Pydantic 模型（非持久化）

以下为项目内部传递数据的结构化类型，继承 `FrozenModel` / `MutableModel`（`vnpy_common/domain/base.py`，跨包共用），不直接对应数据库表：

| 类名 | 定义文件 | 用途 |
|------|----------|------|
| `StockItem` | `vnpy_ashare/domain/symbols/stock.py` | A 股标的统一模型（symbol, exchange, name） |
| `QuoteSnapshot` | `vnpy_ashare/domain/market/quote_snapshot.py` | TickFlow / Redis 行情快照 |
| `QuoteRow` | `vnpy_ashare/domain/market/quote_row.py` | 全市场行情行（选股 / 雷达 / 缓存共用） |
| `ScreenerResultRow` | `vnpy_ashare/domain/screener/result_row.py` | 选股结果结构化行（`quote` + `scores` + `tags`）；`ScreenerRunResult` / `ScreeningResultContext` / 落库 `rows` 均为此类型 |
| `DepthSnapshot` | `vnpy_ashare/domain/market/depth_snapshot.py` | 五档盘口快照（bid/ask 各 5 档） |
| `SignalSnapshot` | `vnpy_ashare/domain/trading/signal_snapshot.py` | 策略信号快照（含强度、锚价、理由） |
| `PeriodBarOverview` | `vnpy_ashare/domain/data/bar.py` | 单标的 K 线概况（symbol, period, start, end, count） |
| `BarMeta` / `BarGapResult` | `vnpy_ashare/domain/data/bar_health.py` | K 线元信息与断层检测 |
| `ChatMessage` | `vnpy_llm/domain/chat.py` | 聊天消息 |
| `AiContextData` | `vnpy_common/ai/protocol.py` | 当前页 / 选中标的 / K 线摘要等 AI 上下文 |
| `BacktestSummary` 等 | `vnpy_ashare/ai/context/store.py` | 终端内存缓存（回测摘要、选股结果；线程安全） |

**约定**：跨模块复用的领域类型优先放入 `domain/`；仅模块内使用的 DTO 可留在原路径但须继承基类；序列化优先用 `vnpy_common/domain/serialize.py` 的 `dump_python` / `dump_json`（读侧 `Model.model_validate`）；复合扁平行（如 `ScreenerResultRow.to_dict()`）可保留专用方法。

---

## 六、总体关系图

```
┌──────────────────────────────────────────────────────────────────┐
│  GUI 层（Views / Pages / Dialogs）                                │
├──────────────────────────────────────────────────────────────────┤
│  内存 Pydantic 模型（StockItem / QuoteSnapshot / SignalSnapshot 等）  │
├──────────┬──────────────────────┬───────────────┬────────────────┤
│ App DB   │ K 线 DB               │ LLM Chat DB   │ Redis           │
│ SQLite   │ SQLite 或 PostgreSQL  │ SQLite        │ (redis-py)      │
│ 原生API  │ Peewee ORM            │ 原生API        │                 │
│          │ ← DATABASE_NAME 控制  │               │                │
├──────────┼──────────────────────┼───────────────┼────────────────┤
│ meta     │ dbbardata             │ sessions      │ zak:quote:{}   │
│ watchlist│ dbtickdata            │ messages      │ zak:rank:*     │
│ universe │ dbbaroverview         │               │ zak:meta:*     │
│ trade_   │ dbtickoverview        │               │                │
│ calendar │                       │               │                │
│ backtest_│                       │               │                │
│ runs     │                       │               │                │
│ screener_│                       │               │                │
│ schemes/ │                       │               │                │
│ recipes/ │                       │               │                │
│ runs     │                       │               │                │
│ stock_   │                       │               │                │
│ note_* / │                       │               │                │
│ reports  │                       │               │                │
├──────────┼──────────────────────┼───────────────┼────────────────┤
│ 自选池   │ K 线 / Tick            │ AI 聊天历史    │ 实时行情快照    │
│ 全A列表  │ 历史市场数据           │               │ 涨幅排名        │
│ 交易日历 │ ★ 唯一可换存储的数据    │               │                │
│ 回测/选股│                       │               │                │
│ 历史     │                       │               │                │
│ 笔记/研报│                       │               │                │
└──────────┴──────────────────────┴───────────────┴────────────────┘
```

---

## 参考

- [看盘页个股笔记](./stock-notes.md)
- [盘中选股](./intraday-screening.md)
- [智能体投研团队](./team-agent.md)
