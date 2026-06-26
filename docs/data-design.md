# 数据设计

元数据与行情**分离**；持久化由 **Alembic + PostgreSQL** 管理（`app` / `chat` / `auth` / `cache` / `system` / `public` schema）。AI 运行时态在 `context_store`（内存）。

---

## 存储总览

| 存储 | 位置 | 内容 |
|------|------|------|
| **PostgreSQL** | `.env` → `DATABASE_URL` | 自选、笔记、选股、AI 会话、Cache、用户偏好、K 线 |
| **QSettings** | 本机 OS 级 | 纯 UI 偏好 |
| **Redis** | `.env` | 行情快照、涨幅榜 |

```text
GUI → Service → Repository → PostgreSQL（app / chat / auth / cache / system）
K 线 → VeighNa → PostgreSQL public（dbbardata 等）
```

入口：`storage/connection.py`、`vnpy_common/storage/session.py`；schema 升级 `cli.py db upgrade`。

---

## App schema 表（`app.*`）

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

QSettings（纯 UI）：窗口几何、列宽、雷达 Tab、共振权重、预测模式等；业务偏好存 PG `auth.user_preferences`（`trading` / `screener` / `radar`（展望策略）/ `notify` / `watchlist` / `emotion` 等 namespace）。`.env` 密钥与 `RECIPE_*`。见 [配置热加载](./config-hot-reload.md)、[多人 PG](./multi-user-pg.md)。

领域模型：`StockItem`、`QuoteSnapshot`、`ScreenerResultRow` 等（`domain/`、`vnpy_common/ai/protocol.py`）。

---

[架构说明](./architecture.md) · [数据流](./data-flow.md)
