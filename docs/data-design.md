# 数据设计

zak 采用**元数据与行情分离**的双存储；建表在代码内 `CREATE TABLE IF NOT EXISTS`，无独立迁移。AI 运行时态在 `context_store`（内存）。

---

## 1. 存储总览

| 存储 | 路径 / 切换 | 内容 |
|------|-------------|------|
| **App DB** | `~/.vntrader/zak.db`（固定 SQLite） | 自选、universe、日历、回测/选股历史、笔记、计划、持仓、信息流 |
| **K 线 DB** | `~/.vntrader/database.db` 或 PostgreSQL | VeighNa `dbbardata` 等；`DATABASE_NAME` 切换 |
| **LLM Chat DB** | `~/.vntrader/llm_chat.db`（固定 SQLite） | AI 会话与消息 |
| **Redis** | `.env` 配置 | 实时行情快照、涨幅排行 |
| **磁盘缓存** | 用户数据目录 | 信号区/持仓短缓存 SQLite |

```text
GUI → Pydantic 模型 → App DB / K线DB / Redis / context_store
```

---

## 2. App DB 表索引（`zak.db`）

| 表 | 用途 | 文档 |
|----|------|------|
| `meta` | 键值（如 `universe_synced_at`） | — |
| `watchlist` | 自选池（≤50） | [自选页](./watchlist.md) |
| `watchlist_groups` / `watchlist_group_members` | 自选 Tab 分组 | 同上 |
| `watchlist_positions` | 持仓记账 | 同上 |
| `universe` | 全 A 列表缓存 | — |
| `trade_calendar` | 交易日历 | K 线健康检测 |
| `backtest_runs` | 回测摘要 | [策略回测](./backtest-ux.md) |
| `screener_schemes` | 条件选股方案 | [盘中选股](./intraday-screening.md) |
| `screener_recipes` | 多因子配方 | 同上 |
| `screener_runs` | 选股运行历史 | [选股 Hub](./screener-hub-guide.md) |
| `stock_note_memos` / `stock_note_entries` / `stock_analysis_reports` | 笔记与研报 | [个股笔记](./stock-notes.md) |
| `trading_plans` / `trading_plan_symbols` | 次日计划 | [交易计划](./trading-plan-journal.md) |
| `notify_delivery_log` | 飞书发送记录 | [消息通知](./notifications.md) |
| `feed_subscriptions` / `feed_items` / `feed_cursors` | B 站信息流 | [信息流](./info-feed.md) |
| `symbol_suspend_days` | 停牌日历 | 硬过滤 |

代码入口：`storage/connection.py`、`app_db.py`、各 `repositories/`。

---

## 3. K 线 DB

VeighNa Peewee 表：`dbbardata`、`dbtickdata`、`dbbaroverview`、`dbtickoverview`。  
访问：`bar_store.py`、`bars.py`；切换 PostgreSQL 见根目录 README。

---

## 4. LLM Chat DB

`sessions` + `messages`（每会话最多读 50 条）。`vnpy_llm/store.py`。

---

## 5. Redis

| Key | 类型 | 用途 |
|-----|------|------|
| `zak:quote:{symbol}` | HASH | 单票快照 |
| `zak:rank:change_pct` | ZSET | 涨幅榜 |
| `zak:meta:*` | STRING | 更新时间、条数 |

配置：`REDIS_URL` 或 `REDIS_HOST` 等（`.env`）。

---

## 6. 非 DB 配置

| 位置 | 内容 |
|------|------|
| QSettings `trading/*` | Profile、风控参数 |
| QSettings `screener/*` | 硬过滤、Hub UI |
| QSettings `notify/*` | 通知订阅 |
| `.env` | 密钥、Webhook、`RECIPE_*` 覆盖 |

---

## 7. 领域模型（内存）

常用：`StockItem`、`QuoteSnapshot`、`ScreenerResultRow`、`SignalSnapshot`、`AiContextData`。  
定义在 `domain/` 与 `vnpy_common/ai/protocol.py`；跨包序列化用 `vnpy_common/domain/serialize.py`。

---

## 参考

[架构说明](./architecture.md) · [数据流](./data-flow.md) · [配置热加载](./config-hot-reload.md)
