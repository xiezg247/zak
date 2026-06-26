# 多用户 + 全量 PostgreSQL 方案（路线 A）

> 内部小团队（3–10 人）共用一套 PostgreSQL；PyQt 桌面客户端直连数据库；**不引入 FastAPI / HTTP 服务层**。

相关文档：[数据设计](./data-design.md) · [架构说明](./architecture.md)

---

## 1. 背景与目标

### 1.1 当前架构（已实现）

| 存储 | 位置 | 访问方式 |
|------|------|----------|
| App / Chat / Auth / Cache / System | 同一 PG 实例，多 schema | `DATABASE_URL`，`vnpy_common/storage/session.py` |
| K 线 | PG `public` | VeighNa `DATABASE_NAME=postgresql` + `POSTGRES_*` |
| 纯 UI 偏好 | QSettings | 本机 per-user（OS 级） |
| 定时任务 | Leader GUI 内 APScheduler | `ZAK_RUN_SCHEDULER` 选主 |

- 应用层 `user_id` 行级隔离（私有表）
- Alembic 管理 schema 变更（`cli.py db upgrade`）

### 1.2 目标

| 项 | 决策 |
|----|------|
| 数据库 | **仅 PostgreSQL** |
| 多用户 | 应用层 `user_id` 行级隔离 |
| 部署 | 内网 PG + Redis；同事各跑 PyQt 客户端 |
| 非目标 | FastAPI、公网多租户、细粒度 RBAC |

### 1.3 目标架构

```text
同事 A（PyQt）──┐
同事 B（PyQt）──┼──→ 内网 PostgreSQL（唯一持久化）
Leader（PyQt）──┘       Redis（行情快照，已有）
                  ↑ 仅 Leader 跑 APScheduler
```

数据路径不变：`UI → Service → Repository → PostgreSQL`。

---

## 2. PostgreSQL 库结构

### 2.1 单库多 Schema

```text
database: zak

schema auth    用户、偏好
schema app     业务元数据
schema chat    AI 对话与 trace
schema cache   可重建的计算/LLM 缓存
schema system  Alembic 版本、scheduler 配置、系统 meta
schema public  K 线（VeighNa vnpy_postgresql：dbbardata 等，与 app 同实例）
```

连接串示例：

```env
DATABASE_URL=postgresql://zak:密码@192.168.1.10:5432/zak
```

客户端启动时：

```sql
SET search_path TO app, chat, auth, cache, system, public;
```

VeighNa K 线驱动（`DATABASE_NAME=postgresql` + `POSTGRES_*`）写入 **`public`** schema，与 `vnpy_postgresql` 默认行为一致；**不**单独建 `bars` schema，避免与已有 K 线表重复。

### 2.2 配置项

| 项 | 说明 |
|----|------|
| `DATABASE_URL` | 业务 + Chat + Cache + K 线共用 PG 实例 |
| `DATABASE_NAME=postgresql` | VeighNa K 线驱动（写入 `public`） |
| `POSTGRES_*` | 与 `DATABASE_URL` 二选一或互补 |
| `REDIS_URL` | 行情快照（内网共享） |

各客户端 `.env` 仍配置 `TICKFLOW_*`、`TUSHARE_*`、`LLM_*`（内网可信）。

---

## 3. 表清单与 `user_id` 归属

### 3.1 用户私有表（加 `user_id UUID NOT NULL`）

主键/唯一约束需包含 `user_id`。

| Schema | 表 | 说明 |
|--------|-----|------|
| app | `watchlist` | 自选池 |
| app | `watchlist_groups` | 自选分组 |
| app | `watchlist_group_members` | 分组成员 |
| app | `watchlist_positions` | 持仓记账 |
| app | `stock_note_memos` | 个股备忘 |
| app | `stock_note_entries` | 笔记条目 |
| app | `stock_analysis_reports` | AI 研报 |
| app | `trading_plans` | 交易计划 |
| app | `trading_plan_symbols` | 计划标的 |
| app | `trading_playbook_discipline_daily` | 纪律 checklist |
| app | `screener_schemes` | 选股方案 |
| app | `screener_recipes` | 多因子配方 |
| app | `screener_runs` | 选股运行历史 |
| app | `backtest_runs` | 回测历史 |
| app | `feed_subscriptions` | 信息流订阅 |
| app | `feed_cursors` | 订阅同步游标 |
| app | `notify_delivery_log` | 通知投递日志 |
| chat | `sessions` | AI 会话 |
| chat | `messages` | AI 消息 |
| chat | `llm_turn_traces` | 对话 trace |
| chat | `llm_tool_calls` | 工具调用审计 |
| auth | `user_preferences` | 用户业务偏好（新建） |
| app | `feed_item_reads` | 已读状态（新建，见 3.3） |

### 3.2 全局共享表（无 `user_id`）

| Schema | 表 | 说明 |
|--------|-----|------|
| app | `universe` | 全 A 股 |
| app | `trade_calendar` | 交易日历 |
| app | `symbol_suspend_days` | 停牌日 |
| app | `tushare_factor_cache` | Tushare 因子缓存 |
| app | `financial_reports` | 财报原始 |
| app | `financial_snapshots` | 财报快照 |
| app | `financial_sync_meta` | 财报同步 meta |
| app | `valuation_history` | 估值历史 |
| app | `disclosure_calendar` | 披露日历 |
| app | `sector_flow_daily` | 板块日频资金 |
| app | `sector_flow_intraday` | 板块 intraday |
| app | `emotion_limit_ladder_daily` | 情绪连板梯队 |
| app | `feed_items` | 信息流内容（按 external_id 去重） |
| public | `dbbardata`、`dbbaroverview`、`dbtickdata`、`dbtickoverview` | VeighNa K 线（全局共享，由 vnpy_postgresql 管理） |
| system | `meta` | 系统级 KV（job 游标、同步水位等） |
| system | `scheduler_config` | 定时任务配置（新建，原 JSON 文件） |

### 3.3 混合 / 特殊

| 表 | 策略 |
|----|------|
| `trading_playbook_sections` | **全局共享**，无 `user_id`；正文来自代码模板（`playbook_templates/`），**用户不可编辑**；切换 Strategy Profile 时自动同步模板 |
| `trading_playbook_discipline_daily` | 用户私有：每日纪律 checklist 勾选状态 |
| `feed_items` | 内容全局共享；**移除 `read_at`**，改 `feed_item_reads(user_id, item_id, read_at)` |
| `cache.*` | 默认可重建、全局共享；若缓存键含用户上下文再加 `user_id` |

### 3.4 Cache Schema 表

| 表 | 说明 |
|----|------|
| `cache.radar_predict_cache` | 雷达预测扫描结果 |
| `cache.radar_horizon_cache` | 雷达展望扫描结果 |
| `cache.radar_ai_hint_cache` | 雷达卡片 AI 摘要 |
| `cache.watchlist_signal_cache` | 自选信号策略缓存 |
| `cache.watchlist_position_cache` | 自选持仓策略缓存 |
| `cache.sector_flow_outlook_llm_cache` | 板块资金展望 LLM 缓存 |

Alembic `004_cache_tables` 预建上述表；部分模块运行时 `CREATE TABLE IF NOT EXISTS` 作兜底。

V1：全局共享，不加 `user_id`；失效后可清空重建。

---

## 4. 用户与鉴权

### 4.1 数据模型

```sql
-- schema auth
CREATE TABLE auth.users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      TEXT UNIQUE NOT NULL,
    display_name  TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,        -- argon2
    is_active     BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE auth.user_preferences (
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    namespace   TEXT NOT NULL,          -- trading | screener | radar | notify | ui
    key         TEXT NOT NULL,
    value_json  JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, namespace, key)
);
```

### 4.2 应用层隔离

```python
# vnpy_common/auth/context.py
current_user_id: ContextVar[str | None]
```

- GUI 启动 → 登录对话框 → 校验 `auth.users` → 设置 `current_user_id`
- Repository 读私有表时统一 `WHERE user_id = %(uid)s`
- 写操作 INSERT 时带 `user_id`

**不做**：JWT、RLS、每人独立 PG 账号（内网小团队不需要）。

### 4.3 账号管理

- V1：`cli.py user create/list` 管理员手动建号
- 可选：首个启动用户引导创建 admin

---

## 5. 存储抽象层

### 5.1 模块结构

```text
packages/vnpy-common/vnpy_common/storage/
  postgres_backend.py   PostgreSQL 实现（psycopg + SQLAlchemy 池）
  pool.py               连接池
  session.py            connect_app / cache_session / chat_session
  dialect.py            executescript 拆分等辅助

packages/vnpy-common/vnpy_common/auth/
  context.py            current_user_id
  users.py              登录校验、密码 hash

alembic/
  alembic.ini
  env.py
  versions/             增量 migration
```

### 5.2 Backend 接口

```python
class DatabaseBackend(Protocol):
    @contextmanager
    def connect(self) -> Iterator[Connection]: ...

    def execute(self, sql: str, params: dict | None = None) -> None: ...
    def fetchall(self, sql: str, params: dict | None = None) -> list[Row]: ...
    def fetchone(self, sql: str, params: dict | None = None) -> Row | None: ...
```

### 5.3 存储入口（已实现）

| 模块 | 说明 |
|------|------|
| `vnpy_ashare/storage/meta.py` | system.meta KV |
| `vnpy_ashare/storage/repository/cache.py` | CacheBaseRepository（cache schema） |
| `vnpy_ashare/storage/repositories/` | app / auth / cache 表读写 |
| `vnpy_common/storage/session.py` | `connect_app` / `cache_session` / `chat_session` |
| `vnpy_llm/chat/store.py`、`trace/persistence.py` | PG `chat` schema |
| `vnpy_ashare/config/bridge.py` | DB 配置只读 `DATABASE_URL` / `POSTGRES_*` |

### 5.4 SQL 约定（PG）

| 项 | 约定 |
|----|------|
| Raw SQL 占位符 | `%s`（psycopg `exec_driver_sql`） |
| SQLAlchemy Core | `insert(...).on_conflict_do_update(...)` 等 |
| 主键自增 | `BIGSERIAL` / `SERIAL` |
| 时间字段 V1 | 部分表仍 `TEXT`（ISO8601）；V2 可统一 `TIMESTAMPTZ` |
| Schema 变更 | Alembic revision，不再运行时 `_ensure_column` |

---

## 6. 用户偏好：业务 PG + 纯 UI 本地

原则：**纯 UI 壳层** → 本机 QSettings（`config/preferences/_local_ui_pref.py`，flat 键）；**业务/策略参数** → `auth.user_preferences`。

### 6.1 迁入 `auth.user_preferences`（业务）

| namespace | 来源模块 | 说明 |
|-----------|----------|------|
| `trading` | `trading_risk.py`, `strategy_profile.py` | 资金/止损、策略画像 |
| `screener` | `hard_filter_prefs.py`, `recipe_tuning_prefs.py` | 选股硬过滤、配方调参 |
| `radar` | `outlook_strategy_prefs.py` | 展望策略类名 |
| `notify` | `notifications/prefs/store.py` | 通知订阅 |
| `emotion` | `emotion_cycle.py` | 情绪周期阈值 |
| `watchlist` | `watchlist_signal.py`（`signal_config`）, `watchlist_position.py`（`position_config`） | 信号/持仓策略参数 |

读写封装：

```python
def get_pref(namespace: str, key: str, default): ...
def set_pref(namespace: str, key: str, value): ...
```

内部读 `current_user_id`，查 `auth.user_preferences`。

### 6.2 保留 QSettings（纯 UI，`_local_ui_pref`）

| 相对键前缀 | 来源模块 | 说明 |
|------------|----------|------|
| `watchlist/signal_panel` 等 | `watchlist_signal.py`, `watchlist_position.py`, `watchlist_groups.py` | 面板开闭、splitter、活跃分组 |
| `watchlist/layout_preset_v1` | `ui/.../watchlist/prefs.py` | 盘中/复盘布局 |
| `watchlist/strategy_workspace_open_v1` | `strategy_workspace_prefs.py` | 策略工作区开闭 |
| `radar/board_mode`, `radar/active_group/*` | `ui/quotes/radar/section_prefs.py` | 雷达版面 Tab |
| `radar/full_refresh_every` | `radar_full_refresh_prefs.py` | 卡片全量刷新间隔 |
| `radar/resonance_weights` | `radar_resonance_prefs.py` | 共振权重滑块 |
| `radar/predict_model_mode` | `predict/predict_prefs.py` | 预测卡模型模式 |
| `llm/nl_screening_confirm_enabled` | `nl_screening_prefs.py` | NL 选股确认弹窗 |
| `llm/team_deep_mode` | `team_prefs.py` | 投研团队深度模式开关 |

另：窗口几何、列宽、Tab 索引等仍直接 QSettings，不经 PG。

---

## 7. 定时任务（Scheduler 选主）

### 7.1 问题

多人各开 GUI 时，若每台都跑 scheduler，会重复执行 `sync_universe`、`batch_download_universe` 等。

### 7.2 方案

```env
# 仅 designated 机器为 true（通常 PG 同机或你的 workstation）
ZAK_RUN_SCHEDULER=true
```

`TaskSchedulerManager.start()`：

```python
if not env_bool("ZAK_RUN_SCHEDULER", default=False):
    return  # 不启动 scheduler
```

### 7.3 Job 分类

| 类型 | 执行方式 |
|------|----------|
| 系统级 | Leader 以 service 身份写全局表 |
| 用户级 | Leader 遍历 `auth.users WHERE is_active`，按 `user_id` 设置 context 后执行 |

用户级 job 示例：

- `sync_bilibili_feed`（按用户 subscriptions）
- `screen_intraday` / `screen_post_close`（按用户 recipe 配置）
- `warm_watchlist_strategy_cache`（按用户 watchlist）

系统级 job 示例：

- `sync_universe`、`batch_download_universe`、`prefetch_tushare`、`sync_sector_flow_daily`

### 7.4 Scheduler 配置持久化

`~/.vntrader/zak_scheduler.json` → `system.scheduler_config`（JSONB，全局一份，Leader 读写）。

---

## 8. Redis

行情快照保持现有全局 key（内网共享）：

```text
zak:quote:{symbol}
zak:rank:change_pct
zak:meta:*
```

V1 不改 key 结构。AI `context_store` 仍内存（per 客户端进程），不跨设备共享。

---

## 9. 配置变更

### 9.1 服务端 / Leader `.env`

```env
DATABASE_URL=postgresql://zak:密码@192.168.1.10:5432/zak
REDIS_URL=redis://192.168.1.10:6379/0
ZAK_RUN_SCHEDULER=true

TICKFLOW_API_KEY=...
TUSHARE_TOKEN=...
LLM_API_BASE=...
LLM_API_KEY=...
```

### 9.2 同事客户端 `.env`

```env
DATABASE_URL=postgresql://zak:密码@192.168.1.10:5432/zak
REDIS_URL=redis://192.168.1.10:6379/0
ZAK_RUN_SCHEDULER=false
# 其余 API Key 各客户端自行配置，或统一用 Leader 机器跑 job 即可
```

---

## 10. 部署

### 10.1 Docker Compose（内网）

```yaml
services:
  postgresql:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    environment:
      POSTGRES_USER: zak
      POSTGRES_PASSWORD: <密码>
      POSTGRES_DB: zak
    volumes: [postgres_data:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

volumes:
  postgres_data:
```

- PG/Redis 端口仅内网可达
- 定期 `pg_dump` 备份

### 10.2 首次初始化（管理员）

```bash
uv run python cli.py db upgrade          # Alembic 建表
uv run python cli.py user create bob secret123
uv run python run.py
```

Leader 机器设置 `ZAK_RUN_SCHEDULER=true` 并保证 PG/Redis 可达；其余客户端默认 `ZAK_RUN_SCHEDULER=false`。多人接入时复用同一 `DATABASE_URL` 与 `cli.py user create` 即可，**不单独维护 onboarding 文档**。

---

## 11. GUI 改动

### 11.1 登录流程

```text
启动 run.py
  → 未登录 / token 过期 → LoginDialog(username, password)
  → 校验 auth.users → set_current_user_id
  → 加载 MainWindow
```

- 「记住用户名」存 QSettings；密码不存
- V1 不提供菜单内「切换用户」；需换账号时退出应用后重新登录

### 11.2 设置页

- 数据库连接只读展示 `DATABASE_URL` 主机（密码打码）
- 可编辑：Redis、TickFlow、LLM 等

---

## 12. 测试策略

| 层 | 方式 |
|----|------|
| 存储 | pytest + testcontainers PostgreSQL |
| 隔离 | 用户 A/B fixture，断言 A 无法读 B 的 watchlist |
| Migration | upgrade from empty |
| Scheduler | mock `ZAK_RUN_SCHEDULER`，断言非 leader 不启动 |
| 回归 | 现有 repository 测试改 PG fixture |

---

## 13. 实施阶段

### Phase 1 — 存储基础

- [x] `vnpy_common/storage/postgres_backend.py` + 连接池
- [x] Alembic 初始 migration（全部 schema + 表）
- [x] Repository / meta / cache stores 切 PG
- [x] VeighNa K 线指同一 PG 实例的 `public` schema
- [x] pytest PG fixture

**验收**：单用户功能与现网一致，数据在 PG。

### Phase 2 — 多用户

- [x] `auth.users` + `user_preferences`
- [x] 私有表加 `user_id`（Alembic revision）
- [x] `current_user_id` ContextVar + Repository 过滤
- [x] LoginDialog + `cli.py user create`
- [x] `feed_item_reads` 替代 `feed_items.read_at`

**验收**：两账号自选/笔记/对话互不可见。

### Phase 3 — 偏好与 Scheduler（约 3–5 天）

- [x] QSettings 业务项迁 `user_preferences`（选股硬过滤 / 配方调参；其余 namespace 可渐进迁移）
- [x] `ZAK_RUN_SCHEDULER` 选主
- [x] 用户级 job 按 user 循环
- [x] `scheduler_config` 入 PG

**验收**：仅 Leader 跑 job；用户 B 登录后看到自己的 screener 硬过滤配置。

### Phase 4 — 文档（约 3–5 天）

- [x] 更新 `.env.example`、本文档
- [~] 内网多人 onboarding 清单：**不做**（当前无多人接入需求；§10.2 保留管理员初始化命令作参考）

**验收**：`db upgrade` 空库可正常启动。

---

## 14. 风险与对策

| 风险 | 对策 |
|------|------|
| Repository 改动面大 | 已分 Phase 落地；raw SQL 统一 `%s` 占位符 |
| 多人同时改同一记录 | V1 last-write-wins；可选 `updated_at` 冲突提示 |
| PG 单点故障 | 内网 `pg_dump` 日备；文档写恢复步骤 |
| DB 密码在客户端 | 内网可信；`.env` 不入 git |
| 非 Leader 误开 scheduler | 默认 `ZAK_RUN_SCHEDULER=false`；日志明确提示 |
| Cache 失效 | 可清空 `cache.*` 后由 Job 预热重建 |

---

## 15. 明确不做（V1）

- FastAPI / REST / WebSocket 服务层
- Row Level Security
- 每人独立 PostgreSQL 账号
- 跨设备 AI context 同步
- 复杂 RBAC（admin/user 两档足够）

---

## 16. 后续可选（V2+）

- `updated_at` 乐观锁 / 冲突合并 UI
- admin  Web 页管理用户（仍不必 Full API，cli 够用）
- 时间字段统一 `TIMESTAMPTZ`
- 独立 `cli.py worker` 进程替代「Leader GUI 跑 scheduler」

---

[数据设计](./data-design.md) · [架构说明](./architecture.md)
