# 性能优化方案

> 面向 **极致短线** 场景的 zak 全链路性能规划。  
> 前提：**仅 PostgreSQL** 作为持久化存储（业务 `app`/`chat`/`auth`/`cache`/`system` + K 线 `public`），**不再支持 SQLite**。  
> 相关：[架构说明](./architecture.md) · [数据设计](./data-design.md) · [数据流](./data-flow.md) · [多人 PG](./multi-user-pg.md)

---

## 1. 背景与目标

### 1.1 业务特征

| 特征 | 性能含义 |
|------|----------|
| 极致短线（1–3 日） | 盘中决策窗口极短，行情新鲜度与选股延迟优先 |
| 全市场 ~5000 标的 | 排行、Recipe、雷达需扫全市场或大规模预过滤 |
| 信号区 ≤10、自选 ≤50 | 热路径规模小，但依赖全市场快照与 K 线批量读 |
| PyQt 桌面 + 内网 PG/Redis | 计算在客户端；Leader 跑定时任务；多人共享 PG |

### 1.2 SLI（验收指标）

| 场景 | 目标 P95 | 极致 P99 |
|------|----------|----------|
| 冷启动 → 首屏可交互 | ≤ 3s | ≤ 2s |
| `collect_quotes` 一轮（TickFlow → Redis） | ≤ 2s | ≤ 1s |
| 市场页定时刷新（30s） | ≤ 500ms | ≤ 200ms |
| 全市场 Recipe 选股（如 `intraday_multi`） | ≤ 3s | ≤ 1s |
| 雷达单卡刷新 | ≤ 800ms | ≤ 400ms |
| 信号区 10 只批量算信号 | ≤ 2s | ≤ 800ms |
| UI 主线程阻塞 | 0 次 >100ms/分钟 | 0 次 >50ms/分钟 |

### 1.3 设计原则

1. **先度量、再优化** — 无基准不改热路径  
2. **计算与 I/O 分离** — 盘中最重 I/O 是 Redis 行情与 PG K 线  
3. **热路径少分配** — 全市场循环避免重复 `dict` 拷贝  
4. **GUI 主线程只渲染** — 重活走 Worker；增量更新 Model  
5. **PG 统一池化** — 业务与 K 线共用连接策略，避免连接风暴  

---

## 2. 存储架构（PostgreSQL Only）

### 2.1 总览

```text
                    ┌─────────────────────────────────────┐
                    │         内网 PostgreSQL (zak)        │
                    │  app / chat / auth / cache / system  │
                    │  public (VeighNa dbbardata 等 K 线)   │
                    └──────────────┬──────────────────────┘
                                   │
     Leader APScheduler ──────────┤ 写：universe、日历、K 线下载、cache
     PyQt GUI (N 客户端) ────────┤ 读：自选、信号、K 线 tail、回测
                                   │
                    ┌──────────────▼──────────────────────┐
                    │              Redis                   │
                    │  zak:quote:* / rank:* / meta:*      │
                    └──────────────┬──────────────────────┘
                                   │
                    TickFlow ──────┘ collect_quotes（Leader）
```

| 层级 | 存储 | 盘中角色 |
|------|------|----------|
| 行情快照 | Redis HASH + ZSET | **热路径**：市场页、选股、雷达 |
| 业务元数据 | PG `app`/`auth` | 自选、计划、偏好；读多写少 |
| K 线 | PG `public.dbbardata` | 信号、pattern、回测；批量 tail 读 |
| 可重建缓存 | PG `cache.*` | 雷达预测、信号磁盘缓存、LLM 中间结果 |
| 运行时态 | 内存 `context_store` | AI 上下文；不持久化 |
| UI 偏好 | QSettings | 列宽、窗口几何；与性能无关 |

**废弃路径（优化方案不再考虑）**：`~/.vntrader/zak.db`、`database.db`、独立 `*.db` 磁盘缓存、`DATABASE_NAME=sqlite`。

客户端启动：

```sql
SET search_path TO app, chat, auth, cache, system, public;
```

连接串见 `.env`：`DATABASE_URL` 或 `POSTGRES_*`；K 线驱动 `DATABASE_NAME=postgresql`（唯一合法值）。

### 2.2 与四档数据流的关系

| 档位 | 时机 | PG 策略 |
|------|------|---------|
| 冷启动 | 打开 App | 只读 PG + Redis；**不**触发全市场重算 |
| 打开页面 | Tab activate | Worker 按需查 PG（K 线 tail、自选列表） |
| 定时任务 | Leader Scheduler | 批量写 PG（K 线、universe）+ Redis |
| 用户操作 | 按钮 / AI | 即时查询；AI 走缓存 schema |

详见 [数据流](./data-flow.md)。

---

## 3. 瓶颈诊断

```text
TickFlow → collect_quotes → Redis (~5k HASH + 10× ZSET 全量重建)
                ↓
         GUI Worker / 选股 Python 循环 (~5k dict 行)
                ↓
         PG K 线 (dbbardata 按 symbol 查询)
                ↓
         PyQt 主线程 (Model reset / Delegate 重绘)
```

| 层级 | 现状（代码锚点） | 主要问题 |
|------|------------------|----------|
| 行情写入 | `quotes/core/redis_store.py` `write_quotes` | 每轮 ~5k HSET + 10 个 ZSET delete/zadd |
| 行情读取 | `get_quotes` 300 批 hgetall + `QuoteSnapshot` 构造 | 对象分配多；同步 enrich Tushare |
| 选股 | `screener/recipe/recipe_runner.py`、各 `dimensions/*` | Python for 循环；`screening_context` 已 preload 但无向量化 |
| 雷达 | `ui/quotes/radar/worker.py` 多卡 Worker | 卡片间重复读 Redis / 映射 |
| K 线 | `data/bars.py`、`load_daily_bars_batch` | 需统一批量 SQL；PG 索引与连接池 |
| PG 业务 | Repository 层分散 session | 多人并发时连接数、长事务 |
| UI | `watchlist_signals/table_view.py` 等 | 全量 refresh；复杂 Delegate 在主线程格式化 |
| 观测 | `vnpy_common/startup_profile.py` | 仅启动分段；缺运行时 trace 与 CI 基准 |

**已有优势（保留）**：`ScreeningContext.preload_*`、`QUOTE_READ_BATCH_SIZE=300`、Worker 后台加载、`download_concurrency` 线程池、`ZAK_STARTUP_PROFILE=1`。

---

## 4. 优化路线

| 路线 | 做法 | 预期收益 | 成本 | 建议 |
|------|------|----------|------|------|
| **A. 渐进优化** | 缓存、批处理、Redis/PG 协议、UI 增量 | 2–4× | 低 | Phase 1 首选 |
| **B. 列存计算层** | Polars 统一 Quote 快照；选股/排行向量化 | 5–15×（计算） | 中 | Phase 2 核心 |
| **C. 原生热路径** | Rust 扩展：硬过滤、TopN、MA 信号 | 10–50×（局部） | 高 | Phase 3 可选 |

**推荐顺序**：A → B；C 仅在 benchmark 证明瓶颈后引入。

---

## 5. 分层方案

### 5.1 行情摄取（TickFlow → Redis）

**目标**：`collect_quotes` P95 ≤ 1s。

1. **采集与 enrich 解耦**  
   - 主路径：TickFlow → Redis（价量字段，<500ms）  
   - 异步 Job：`enrich_quotes_with_tushare_factors` 写扩展字段  
   - 盘中最敏感价量/涨幅；Tushare 因子允许 1–5min 滞后  

2. **ZSET 增量更新**  
   - 现状：每字段 `delete` + 全量 `zadd`  
   - 改为差分 `ZADD` 或 Job 内预计算 Top-N 写入 `zak:rank:precomputed:{field}`  

3. **Redis 读路径瘦身**  
   - 评估短 field key 或 msgpack/orjson blob（单次 GET）  
   - 保持 `QUOTE_READ_BATCH_SIZE` 分批，避免 socket 超时  

4. **进程内 L1 行情缓存（Leader）**  
   - `collect_quotes` → Redis 写完后 `swap_quotes`（`ZAK_QUOTE_L1_CACHE=1`）  
   - `RedisQuoteStore.get_quotes` / `list_all_rank_symbols` / `load_market_quote_rows` 优先读 L1  
   - 同机 GUI 与 collect 共享进程时零 Redis 读；跨进程仍走 Redis  

5. **collect enrich 解耦**  
   - `ZAK_COLLECT_DEFER_ENRICH=1`：采集主路径跳过 Tushare enrich，读路径 `fill_missing_tushare_factors` 补全  

### 5.2 计算层（选股 / 雷达 / 排行）

**目标**：`intraday_multi` P95 ≤ 1s。

1. **列存快照（Phase B）**  
   - `load_screening_quote_snapshot()` 产出 `pl.DataFrame`  
   - 硬过滤、动量、换手、板块强度 → `filter → with_columns → sort → head`  
   - `ScreeningContext` 持有同一 DataFrame，维度只读列  

2. **预计算榜**  
   - `collect_quotes` 或独立 Job 写入 Redis 预计算 Top-N  
   - 市场页 / 雷达只读榜，不在客户端对 5000 行排序  

3. **硬过滤一次化**  
   - `passes_screening_hard_filter` 向量化（ST、停牌、成交额、市值）  
   - `symbol_suspend_days`、`universe.list_date` 在 preload 阶段 join  

4. **维度并行**  
   - CPU 密集维度：Polars lazy 单进程优先于多进程 pickle  
   - I/O 密集（K 线 tail）：保留 `ThreadPoolExecutor`，上限见 `config/constants/concurrency.py`  

5. **K 线 tail 内存 LRU**  
   - `load_history_bars_map` 仅对 `pool_size × 2` 候选拉取（已有）  
   - 对 PG 结果做进程内 LRU，避免同 Recipe 内重复查库  

### 5.3 PostgreSQL（唯一持久化）

**目标**：10 只信号 batch P95 ≤ 800ms；pattern 扫描 500 只 ≤ 3s。

#### 5.3.1 连接与池化

| 项 | 建议 |
|----|------|
| 客户端 | SQLAlchemy `QueuePool`：`pool_size=5`，`max_overflow=10`，`pool_pre_ping=True` |
| 多人部署 | **PgBouncer**（transaction 模式）；应用侧控制并发 Worker 数 |
| search_path | 连接建立时一次 `SET search_path`，避免每查询重复 |
| 长事务 | 禁止 GUI 主线程持锁；批量 Job 分块 commit |

#### 5.3.2 K 线（`public.dbbardata`）

1. **批量 tail 查询**  
   ```sql
   -- 示意：按 symbol 列表取最近 N 根日 K
   SELECT symbol, exchange, datetime, open_price, high_price, low_price, close_price, volume
   FROM dbbardata
   WHERE interval = 'd' AND (symbol, exchange) IN (...)
   ORDER BY symbol, exchange, datetime DESC;
   ```  
   应用层按 symbol 分组；策略信号用 numpy 向量化 MA/突破。

2. **索引**  
   - 复合索引：`(interval, symbol, exchange, datetime DESC)` 或 VeighNa 已有主键对齐  
   - 定期 `ANALYZE`；大表可考虑 BRIN（按 datetime）  

3. **分区（可选，数据量 > 千万行）**  
   - 按 `datetime` 范围分区；历史分区只读  

4. **读副本（可选）**  
   - GUI 只读查询走 replica；Leader 写 primary  

#### 5.3.3 业务与 cache schema

| Schema | 优化点 |
|--------|--------|
| `app.universe` / `trade_calendar` | 冷启动一次性加载进内存；变更仅 Scheduler 触发 |
| `app.symbol_suspend_days` | 硬过滤 preload 为 `frozenset`；Repository 层进程缓存 |
| `cache.*` | 可重建；大 JSON 用 `JSONB` + GIN（按需）；设 TTL 列定期清理 |
| `auth.user_preferences` | 登录后整包加载；写时 invalidate |

#### 5.3.4 不再使用的 SQLite 优化项

以下**不纳入**本方案：WAL、`PRAGMA cache_size`、单机文件锁重试、`.db` 磁盘 cache 文件。  
原 `sqlite_cache_session` / 独立 `*.db` 均已迁入 PG `cache` schema（见 [多人 PG §3.4](./multi-user-pg.md#34-cache-schema-表原独立-db-文件)）。

### 5.4 UI 层（PyQt）

**目标**：主线程无 >50ms 阻塞。

1. **Model 增量更新** — `dataChanged` 按行/列；避免 `beginResetModel` 全刷  
2. **Worker 合并去抖** — 同页 30s 内多次 refresh 合并；Tab deactivate 时 cancel Worker  
3. **共享快照** — 雷达多卡共用一次 `load_screening_quote_snapshot`  
4. **Delegate 预计算** — 信号 strength、涨跌色等在 Worker 内格式化为字符串  
5. **虚拟化** — 市场排行 >200 行：固定行高 + 按需 fetch  

### 5.5 AI / LLM（非盘中热路径）

- 盘中禁止同步 LLM 阻塞 GUI  
- 工具结果写 `cache.*` 或 `context_store` 摘要  
- Team analysis 限盘后或显式触发  

### 5.6 调度与多用户

- **仅 Leader** 跑 APScheduler（`collect_quotes`、K 线下载、universe 同步）  
- 非 Leader 客户端：Redis + PG 只读，不连 TickFlow  
- 盘后 bulk 与盘中轻量任务错峰  

---

## 6. 观测与回归

### 6.1 已有

| 工具 | 启用 | 说明 |
|------|------|------|
| 启动分段 | `ZAK_STARTUP_PROFILE=1` | `vnpy_common/startup_profile.py` |
| 运行时 trace | `ZAK_PERF_TRACE=1` | `vnpy_common/perf_trace.py`；热路径 span 见下表 |
| synthetic 基准 | `uv run python bench/run_hotpaths.py` | 见 [`bench/README.md`](../bench/README.md) |

**已接入 span**（`ZAK_PERF_TRACE=1` 时输出到 stdout）：

| span 前缀 | 模块 |
|-----------|------|
| `collect.*` | `jobs/quotes/collect.py` |
| `load_market_quote_rows` / `quotes.*` | `screener/data/quotes_loader.py` |
| `run_recipe.*` / `recipe.*` | `screener/recipe/recipe_runner.py` |
| `radar.load_cards[*]` | `quotes/radar/loaders/load.py` |
| `quotes.l1_hit` | L1 全市场快照命中 |

### 6.2 待建设

| 工具 | 用途 |
|------|------|
| ~~`ZAK_PERF_TRACE=1`~~ | 已落地，见 §6.1 |
| ~~`bench/` + pytest~~ | 已落地：`bench/run_hotpaths.py`、`tests/bench/test_hotpath_bench.py` |
| Py-Spy / cProfile | 季度火焰图 |
| PG `pg_stat_statements` | 慢查询 Top-N |
| Redis `INFO` | commands/sec、latency |

### 6.3 基准数据集

- 脱敏 1 交易日 Redis dump  
- 对应 PG `dbbardata` slice + `universe` 快照  
- 脚本一键还原，保证优化可复现  

---

## 7. 分阶段路线图

### Phase 0 — 基线（约 1 周）

- [x] 全链路打点（`ZAK_PERF_TRACE` + 热路径 span）  
- [x] synthetic 基准脚本（`bench/run_hotpaths.py`）  
- [ ] 记录 P50/P95：启动、collect、选股、雷达、信号、PG 慢查询  
- [ ] 输出 Top 5 热点报告  

### Phase 1 — Quick Wins（约 2–3 周）

- [x] 进程内 L1 quote cache（`ZAK_QUOTE_L1_CACHE` + `quote_l1_cache.py`）  
- [x] collect enrich 可 defer（`ZAK_COLLECT_DEFER_ENRICH`）  
- [x] 市场表 `render_table` 同行同序时增量 `apply_row`  
- [x] PG 连接池 env 可调（`POSTGRES_POOL_SIZE` / `POSTGRES_MAX_OVERFLOW`）  
- [x] K 线 batch 读前预热 overview（`load_daily_bars_batch`）  
- [x] 行情 Worker 合并（`_pending_quote_refresh`）  
- [x] `purge_stale_cache` 清理 cache schema 过期行  
- [ ] Redis 读路径进一步瘦身（msgpack / 短 field key）  

**预期**：整体体感 ~2×；collect 与市场刷新明显改善。

### Phase 2 — 列存选股引擎（约 3–5 周）

- [ ] Polars 引入（边界：`screener/`、`quotes/rank/`）  
- [ ] `QuoteSnapshot` ↔ DataFrame 桥接  
- [ ] 硬过滤 + 主要维度向量化  
- [ ] Redis 预计算榜  
- [ ] Feature flag：`ZAK_SCREENER_ENGINE=polars|python`  

**预期**：Recipe 选股 5–10×。

### Phase 3 — 极致路径（可选，4+ 周）

- [ ] Rust 扩展：`hard_filter`、`rank_topn`、`double_ma_signal`  
- [ ] Redis Streams 推送替代部分轮询  
- [ ] PG 读副本 + PgBouncer 生产化  
- [ ] quote-ingest 独立进程（TickFlow 与 GUI 隔离）  

---

## 8. 配置参考

`.env` 片段（在 [`.env.example`](../.env.example) 基础上扩展）：

```env
# 存储（仅 PostgreSQL）
DATABASE_NAME=postgresql
DATABASE_URL=postgresql://zak:***@host:5432/zak

# 并行 I/O（已有，可按核数微调）
DOWNLOAD_MAX_WORKERS=4
CONTINUATION_BATCH_MAX_WORKERS=6
RADAR_BOARD_MAX_WORKERS=6

# 性能（Phase 0/1）
ZAK_STARTUP_PROFILE=0
ZAK_PERF_TRACE=0
ZAK_QUOTE_L1_CACHE=0
ZAK_COLLECT_DEFER_ENRICH=0
```

---

## 9. 风险与边界

| 风险 | 缓解 |
|------|------|
| L1 与 Redis 不一致 | `meta:seq`；fallback Redis |
| 异步 enrich 因子滞后 | 盘前 warmup；UI 标注数据时间 |
| Polars 引入成本 | 仅 screener 边界；python 回退 |
| 多人 PG 连接风暴 | PgBouncer + Worker 上限 |
| PG K 线表膨胀 | 分区 + 归档；盘后维护窗口 |

**明确不做（YAGNI）**：

- 恢复或兼容 SQLite 路径  
- 全面 PyQt → Web 重写  
- Phase 1 引入 Rust  
- 无度量的大范围重构  

---

## 10. 验收清单（极致短线）

- [ ] 9:30–11:30 连续 2h，主线程无可见卡顿  
- [ ] 行情 `meta:updated_at` lag < 采集间隔 + 1s  
- [ ] Hub「极致短线 unified」→ 结果 P95 < 2s  
- [ ] 雷达 `leader_pick` P95 < 500ms（预计算榜启用后）  
- [ ] 信号区 10 只手动刷新 P95 < 1s  
- [ ] `bench/` CI 无回归  
- [ ] 3 客户端并发读 PG，无连接耗尽  

---

## 参考

- [交易体系 · 极致短线](./trading-system.md)  
- [盘中选股](./intraday-screening.md)  
- [雷达选龙头](./radar-leader-screening.md)  
- [多人 PG 方案](./multi-user-pg.md)  
- 代码：`quotes/core/redis_store.py`、`screener/data/screening_context.py`、`data/download_concurrency.py`、`vnpy_common/startup_profile.py`
