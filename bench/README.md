# 性能基准（Phase 0）

Synthetic 模式覆盖：

- `quote_snapshot_roundtrip` — Redis HASH 序列化/反序列化
- `market_rank_sort` — 全市场涨幅排序取 Top 200
- `row_filter_scan` — 模拟硬过滤的行扫描（不访问 PG）

## 运行

```bash
# 默认：5000 标的 × 5 轮
uv run python bench/run_hotpaths.py

# 自定义规模
uv run python bench/run_hotpaths.py --symbols 5000 --rounds 10
```

## 集成模式（需环境就绪）

```bash
# Redis 已有全市场行情
ZAK_PERF_TRACE=1 uv run python bench/run_hotpaths.py --integration redis

# 跑 intraday_multi 配方（需 Redis + PG）
ZAK_PERF_TRACE=1 uv run python bench/run_hotpaths.py --integration recipe --recipe intraday_multi
```

Phase 1 Leader 推荐 `.env`：

```env
ZAK_PERF_PROFILE=leader
```

或逐项开启：

```env
ZAK_QUOTE_L1_CACHE=1
ZAK_COLLECT_DEFER_ENRICH=1
ZAK_QUOTE_REDIS_NOTIFY=1
ZAK_RANK_PRECOMPUTE=1
ZAK_RANK_ORDERED_LIST=1
ZAK_REDIS_QUOTE_COMPACT=1
ZAK_REDIS_QUOTE_BLOB=1
```

### 独立采集进程（与 GUI 隔离）

Leader 机器上循环采集（不启动 PyQt）：

```bash
# 单次
uv run zak job run collect_quotes --force

# 交易时段内每 30s（示例）
while true; do uv run zak job run collect_quotes; sleep 30; done
```

GUI 客户端开启 `ZAK_QUOTE_REDIS_NOTIFY=1` 后，收到 Pub/Sub 推送即刷新，可拉长 `_quote_timer` 间隔。

## 运行时 tracing

热路径已接入 `vnpy_common.perf_trace`（`ZAK_PERF_TRACE=1`）：

| span | 位置 |
|------|------|
| `collect.*` | `jobs/quotes/collect.py` |
| `load_market_quote_rows` / `quotes.*` | `screener/data/quotes_loader.py` |
| `run_recipe.*` / `recipe.*` | `screener/recipe/recipe_runner.py` |
| `radar.load_cards[*]` | `quotes/radar/loaders/load.py` |

### 基线报告

```bash
# synthetic + Top 5 热点（离线）
uv run python bench/report_baseline.py

# 追加 Redis / intraday_multi / leader_pick（需环境）
ZAK_PERF_TRACE=1 uv run python bench/report_baseline.py --live --output bench/reports/latest.txt
```

详见 [性能优化方案](../docs/performance-optimization.md)。
