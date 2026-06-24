# 数据设计

元数据与行情**分离**；建表 `CREATE TABLE IF NOT EXISTS`（无独立迁移）。AI 运行时态在 `context_store`（内存）。

---

## 存储总览

| 存储 | 位置 | 内容 |
|------|------|------|
| **App DB** | `~/.vntrader/zak.db`（固定 SQLite） | 自选、universe、回测/选股历史、笔记、计划、持仓、信息流 |
| **K 线 DB** | `database.db` 或 PostgreSQL | VeighNa `dbbardata` 等；`DATABASE_NAME` 切换 |
| **LLM Chat DB** | `~/.vntrader/llm_chat.db` | AI 会话 `sessions` / `messages` |
| **Redis** | `.env` | 行情快照、涨幅榜 |
| **磁盘缓存** | 用户数据目录 | 信号区/持仓短缓存 |

```text
GUI → Pydantic → App DB / K线DB / Redis / context_store
```

入口：`storage/connection.py`、`app_db.py`、`repositories/`；K 线 `bar_store.py`、`bars.py`。

---

## App DB 表（`zak.db`）

| 表 | 文档 |
|----|------|
| `watchlist` / `watchlist_groups*` / `watchlist_positions` | [自选页](./watchlist.md) |
| `backtest_runs` | [策略回测](./backtest-ux.md) |
| `screener_schemes` / `screener_recipes` / `screener_runs` | [盘中选股](./intraday-screening.md) |
| `stock_note_*` / `stock_analysis_reports` | [个股笔记](./stock-notes.md) |
| `trading_plans` / `trading_plan_symbols` | [交易计划](./trading-plan-journal.md) |
| `notify_delivery_log` | [通知](./notifications.md) |
| `feed_*` | [信息流](./info-feed.md) |
| `universe` / `trade_calendar` / `meta` / `symbol_suspend_days` | universe 同步、日历、硬过滤 |

---

## Redis 与其它配置

| Key | 用途 |
|-----|------|
| `zak:quote:{symbol}` | 单票 HASH 快照 |
| `zak:rank:change_pct` | 涨幅 ZSET |
| `zak:meta:*` | 更新时间等 |

QSettings：`trading/*`（Profile、风控）、`screener/*`（硬过滤）、`notify/*`；`.env` 密钥与 `RECIPE_*`。见 [配置热加载](./config-hot-reload.md)。

领域模型：`StockItem`、`QuoteSnapshot`、`ScreenerResultRow` 等（`domain/`、`vnpy_common/ai/protocol.py`）。

---

[架构说明](./architecture.md) · [数据流](./data-flow.md)
