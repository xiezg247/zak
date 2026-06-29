# 部署配置（client / leader）

面向极致短线场景的角色拆分与性能开关。详见 [性能优化方案](./performance-optimization.md) 与 [bench/README](../bench/README.md)。

---

## 角色拓扑

```text
Leader（无 GUI）          Redis              GUI 客户端（PyQt）
collect + Scheduler  ──►  行情快照  ◄──  只读 + Pub/Sub 刷新
         │                                    │
         └──────────── PostgreSQL ────────────┘
```

| 角色 | 进程 | 职责 |
|------|------|------|
| Leader | `zak job run collect_quotes` 或 Scheduler | 写 Redis、盘后 Job、K 线下载 |
| GUI client | `uv run python cli.py` | 看盘、雷达、选股、信号 |

---

## GUI 客户端 `.env`

```env
# 性能预设：只读行情 + Pub/Sub
ZAK_PERF_PROFILE=client

# 不在本进程采集（由 Leader 写入 Redis）
ZAK_QUOTE_COLLECT_MODE=external
ZAK_QUOTE_REDIS_NOTIFY=1

# 不跑 APScheduler（定时任务在 Leader）
# ZAK_RUN_SCHEDULER 不设置或 false

# 共享 I/O 线程池（雷达/选股/TickFlow 共用）
ZAK_GLOBAL_IO_MAX_WORKERS=6

# 连接池（多人 PG 时按需调）
POSTGRES_POOL_SIZE=5
POSTGRES_MAX_OVERFLOW=10
```

---

## Leader 机器 `.env`

```env
ZAK_PERF_PROFILE=leader
ZAK_RUN_SCHEDULER=true
ZAK_QUOTE_COLLECT_MODE=external

ZAK_QUOTE_L1_CACHE=1
ZAK_COLLECT_DEFER_ENRICH=1
ZAK_RANK_PRECOMPUTE=1
ZAK_RANK_ORDERED_LIST=1
ZAK_RANK_INCREMENTAL=1
ZAK_REDIS_QUOTE_BLOB=1

ZAK_GLOBAL_IO_MAX_WORKERS=8
```

### 独立采集循环（交易时段）

```bash
while true; do uv run zak job run collect_quotes; sleep 30; done
```

`external` 模式下 Scheduler **不会**再调度 `collect_quotes`，避免双采集。

---

## 单机开发（GUI 内嵌采集）

```env
ZAK_PERF_PROFILE=leader
ZAK_QUOTE_COLLECT_MODE=embedded
ZAK_RUN_SCHEDULER=true
```

适合本机调试；生产建议 client + 独立 Leader。

---

## 验收

```bash
# 运行时 span
ZAK_PERF_TRACE=1 uv run python cli.py

# live 基线（盘中，Redis 已有行情）
ZAK_PERF_TRACE=1 uv run python bench/report_baseline.py --live --check --output bench/reports/latest.txt
```

目标 SLI 见 [性能优化方案 §1.2](./performance-optimization.md)。
