# 数据设计

vnpy_zak 使用 **三个独立的 SQLite 数据库**（共 10 张表）和 **一个 Redis 缓存层**。所有建表语句均通过 `CREATE TABLE IF NOT EXISTS` 在代码中内联执行，没有独立的数据库迁移文件。

---

## 一、App DB：项目元数据

| 属性 | 值 |
|------|-----|
| 数据库文件 | `~/.vntrader/vnpy_zak.db` |
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

---

## 二、VeighNa K 线 DB：市场数据

| 属性 | 值 |
|------|-----|
| 数据库文件 | `~/.vntrader/database.db` |
| ORM/方式 | **Peewee ORM**（`vnpy_sqlite` 包） |
| 定义文件 | `vnpy_sqlite/sqlite_database.py`（外部依赖） |
| 本项目引用 | `vnpy_ashare/bar_store.py`、`vnpy_ashare/bars.py` |

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

**当前状态：** `sessions` 表已定义但 UI 未暴露多会话切换（P2 规划中）。`ChatStore.get_or_create_default_session()` 总是返回最近活跃的单一会话。

---

## 四、Redis 缓存层

| 属性 | 值 |
|------|-----|
| 定义文件 | `vnpy_ashare/quotes/redis_store.py` |
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

## 五、内存 Dataclass 模型（非持久化）

以下为项目内部传递数据的结构化类型，不直接对应数据库表：

| 类名 | 定义文件 | 用途 |
|------|----------|------|
| `StockItem` | `vnpy_ashare/models.py:23` | A 股标的统一模型（symbol, exchange, name） |
| `QuoteSnapshot` | `vnpy_ashare/quotes/snapshot.py:8` | TickFlow / Redis 行情快照（14 个字段） |
| `DepthSnapshot` | `vnpy_ashare/quotes/depth_snapshot.py:8` | 五档盘口快照（bid/ask 各 5 档） |
| `PeriodBarOverview` | `vnpy_ashare/bar_store.py:22` | 单标的 K 线概况（symbol, period, start, end, count） |
| `BarMeta` | `vnpy_ashare/bar_health.py:19` | K 线元信息（start, end, count） |
| `BarGapResult` | `vnpy_ashare/bar_health.py:33` | K 线断层检测结果 |
| `GapRange` | `vnpy_ashare/bar_health.py:27` | 断层区间 |
| `ChatMessage` | `vnpy_llm/store.py:36` | 聊天消息（role, content, created_at） |

---

## 六、总体关系图

```
┌──────────────────────────────────────────────────────────────────┐
│  GUI 层（Views / Pages / Dialogs）                                │
├──────────────────────────────────────────────────────────────────┤
│  内存 Dataclass（StockItem / QuoteSnapshot / ChatMessage 等）       │
├──────────┬──────────────┬───────────────┬────────────────────────┤
│ App DB   │ K 线 DB       │ LLM Chat DB   │ Redis                  │
│ SQLite   │ SQLite        │ SQLite        │ (redis-py)             │
│ 原生API  │ Peewee ORM    │ 原生API        │                        │
├──────────┼──────────────┼───────────────┼────────────────────────┤
│ meta     │ dbbardata     │ sessions      │ zak:quote:{symbol}     │
│ watchlist│ dbtickdata    │ messages      │ zak:rank:change_pct    │
│ universe │ dbbaroverview │               │ zak:meta:*             │
│ trade_   │ dbtickoverview│               │                        │
│ calendar │               │               │                        │
├──────────┼──────────────┼───────────────┼────────────────────────┤
│ 自选池   │ K 线 / Tick    │ AI 聊天历史    │ 实时行情快照 + 涨幅排名    │
│ 全A列表  │ 历史市场数据   │               │                        │
│ 交易日历 │               │               │                        │
└──────────┴──────────────┴───────────────┴────────────────────────┘
```
